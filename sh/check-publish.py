#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Check that the source version is newer than published releases unless republishing is requested.'

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from packaging.version import Version


def main() -> None:
  args = sys.argv[1:]
  republish = bool(args and args[-1] == '-republish')
  if republish: args.pop()
  if len(args) != 3:
    sys.exit(f'usage: {sys.argv[0]} registry package version [-republish]')
  registry, package, version = args
  current = Version(version)
  try:
    with urlopen(f'{registry}/pypi/{package}/json', timeout=30) as response:
      releases = json.load(response)['releases']
  except HTTPError as e:
    if e.code == 404:
      print(f'New project: {package} {version} on {registry}.')
      return
    sys.exit(f'Cannot check published versions: {e}')
  except URLError as e:
    sys.exit(f'Cannot check published versions: {e}')

  latest = max((Version(v) for v in releases), default=None)
  if latest is not None:
    if current < latest:
      sys.exit(f'Source version {version} is older than published version {latest}; increase the version.')
    if current == latest:
      if not republish:
        sys.exit(f'Version {version} is already published; increase the version or specify -republish.')
      print(f'Republishing {package} {version}.')
      return
  print(f'New release: {package} {version}.')


if __name__ == '__main__': main()
