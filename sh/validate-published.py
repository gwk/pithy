#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Install and validate a published release in an isolated environment.'

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main() -> None:
  if len(sys.argv) < 3:
    sys.exit(f'usage: {sys.argv[0]} {{test|prod}} package [extra-import ...]')
  stage, package, *extra_imports = sys.argv[1:]
  registries = {'test':'https://test.pypi.org', 'prod':'https://pypi.org'}
  if stage not in registries:
    sys.exit(f'error: unknown stage: {stage}')
  if re.fullmatch(r'[a-z][a-z0-9_]*', package) is None:
    sys.exit(f'error: invalid package name: {package}')
  registry = registries[stage]
  script_dir = Path(__file__).resolve().parent
  try:
    version = subprocess.check_output(
      [sys.executable, '-I', str(script_dir / 'extract-version.py'), package], text=True).strip()
  except subprocess.CalledProcessError as e:
    sys.exit(e.returncode)

  # Select the target wheel from the requested registry; resolve dependencies from production PyPI.
  try:
    with urlopen(f'{registry}/pypi/{package}/{version}/json', timeout=30) as response:
      release = json.load(response)
  except (HTTPError, URLError) as e:
    sys.exit(f'Cannot fetch {package} {version} from {registry}: {e}')
  wheels = [f for f in release['urls'] if f['filename'].endswith('-py3-none-any.whl') and not f['yanked']]
  if len(wheels) != 1:
    sys.exit(f'Expected one non-yanked pure Python wheel for {package} {version}; found {len(wheels)}.')
  wheel = wheels[0]
  artifact_url = f"{wheel['url']}#sha256={wheel['digests']['sha256']}"

  # Ignore local configuration and cooldowns, and prevent local Python modules from shadowing the installation.
  env = os.environ.copy()
  for name in ('UV_INDEX', 'UV_DEFAULT_INDEX', 'UV_INDEX_URL', 'UV_EXTRA_INDEX_URL', 'UV_FIND_LINKS', 'UV_NO_INDEX',
    'UV_EXCLUDE_NEWER', 'UV_EXCLUDE_NEWER_PACKAGE'):
    env.pop(name, None)
  result = subprocess.run([
    'uv', 'run', '--no-project', '--no-config', '--isolated', '--refresh', '--python', '3.14',
    '--default-index', 'https://pypi.org/simple/', '--with', f'{package} @ {artifact_url}',
    'python', '-I', str(script_dir / 'validate-installed.py'), package, version, *extra_imports,
  ], cwd=script_dir.parent, env=env)
  sys.exit(result.returncode)


if __name__ == '__main__': main()
