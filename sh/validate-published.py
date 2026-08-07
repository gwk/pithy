#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Install and validate a published release in an isolated environment.'

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
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
  wheel = select_wheel(package, version, files=release['urls'])
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


def select_wheel(package:str, version:str, files:list[dict[str,Any]]) -> dict[str,Any]:
  '''
  Select the wheel to validate from the files of a release.
  A pure Python release has a single wheel. A native release has one per platform, so select the first that this interpreter
  supports, in its order of preference; that requires `packaging`, which the project environment provides.
  '''
  wheels = [f for f in files if f['filename'].endswith('.whl') and not f['yanked']]
  if len(wheels) == 1 and wheels[0]['filename'].endswith('-py3-none-any.whl'): return wheels[0]
  if not wheels: sys.exit(f'No non-yanked wheel found for {package} {version}.')

  try:
    from packaging.tags import sys_tags
    from packaging.utils import parse_wheel_filename
  except ImportError:
    sys.exit(f'Selecting a native wheel of {package} {version} requires `packaging` in the selected Python environment.')
  wheels_by_tag = {tag: f for f in wheels for tag in parse_wheel_filename(f['filename'])[3]}
  for tag in sys_tags():
    try: return wheels_by_tag[tag]
    except KeyError: pass
  names = ', '.join(f['filename'] for f in wheels)
  sys.exit(f'No wheel of {package} {version} supports this interpreter and platform; found: {names}.')


if __name__ == '__main__': main()
