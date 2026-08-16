#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Check whether a CPython point version is the latest release in its major.minor series.
Queries the CPython repository tags with `git ls-remote` and prints a warning to stderr if there is a more recent version.
Final releases are tagged `vX.Y.Z`; prereleases carry an `a`/`b`/`rc` suffix and are excluded by the tag pattern.
Network or git failures produce a note and a zero exit so that build scripts can call this unconditionally;
only a usage error exits nonzero. This script runs before our Python is built, so it is stdlib-only.
'''

from __future__ import annotations  # This script may run on older system python3 (macOS ships 3.9).

import re
from subprocess import DEVNULL, PIPE, run, SubprocessError
from sys import argv, exit, stderr


cpython_url = 'https://github.com/python/cpython'


def main() -> None:
  if len(argv) != 2: exit(f'usage: {argv[0]} MAJOR.MINOR.POINT')
  expected = argv[1]
  m = re.fullmatch(r'(\d+\.\d+)\.\d+', expected)
  if not m: exit(f'error: malformed python version: {expected!r}; expected MAJOR.MINOR.POINT.')
  series = m[1]
  latest = latest_point_release(series)
  if latest is None:
    print(f'Note: could not determine the latest python {series} release; skipping version check.', file=stderr)
  elif version_key(latest) > version_key(expected):
    print(f'WARNING: expected python {expected} is outdated; the latest {series} release is {latest}.', file=stderr)
  else:
    print(f'Python {expected} is the latest {series} release.')


def latest_point_release(series:str) -> str|None:
  'Return the latest final release of `series` (e.g. "3.14"), or None if the query fails or finds no tags.'
  cmd = ['git', 'ls-remote', '--tags', cpython_url, f'refs/tags/v{series}.*']
  try: proc = run(cmd, stdout=PIPE, stderr=DEVNULL, timeout=30, text=True)
  except (OSError, SubprocessError): return None
  if proc.returncode != 0: return None
  # The `$` anchor excludes prerelease tags and the peeled `^{}` refs of annotated tags.
  versions:list[str] = re.findall(rf'refs/tags/v({re.escape(series)}\.\d+)$', proc.stdout, re.M)
  if not versions: return None
  return max(versions, key=version_key)


def version_key(version:str) -> tuple[int,...]:
  return tuple(int(part) for part in version.split('.'))


if __name__ == '__main__': main()
