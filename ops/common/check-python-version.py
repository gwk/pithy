#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Check whether a CPython point version is the latest release in its major.minor series.
Queries the CPython repository tags with `git ls-remote` and prints a warning to stderr if there is a more recent version.
Prereleases carry an `a`/`b`/`rc` suffix and are considered only when the expected version is a prerelease.
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
  m = re.fullmatch(r'(\d+\.\d+)\.\d+((?:a|b|rc)\d+)?', expected)
  if not m: exit(f'error: malformed python version: {expected!r}; expected MAJOR.MINOR.POINT with an optional aN, bN or rcN suffix.')
  series = m[1]
  latest = latest_point_release(series, prereleases=bool(m[2]))
  if latest is None:
    print(f'Note: could not determine the latest python {series} release; skipping version check.', file=stderr)
  elif version_key(latest) > version_key(expected):
    print(f'WARNING: expected python {expected} is outdated; the latest {series} release is {latest}.', file=stderr)
  else:
    print(f'Python {expected} is the latest {series} release.')


def latest_point_release(series:str, prereleases:bool=False) -> str|None:
  'Return the latest eligible release of `series` (e.g. "3.14"), or None if the query fails or finds no tags.'
  cmd = ['git', 'ls-remote', '--tags', cpython_url, f'refs/tags/v{series}.*']
  try: proc = run(cmd, stdout=PIPE, stderr=DEVNULL, timeout=30, text=True)
  except (OSError, SubprocessError): return None
  if proc.returncode != 0: return None
  # Exclude peeled refs of annotated tags; opt into prereleases only when requested.
  suffix = r'(?:(?:a|b|rc)\d+)?' if prereleases else ''
  versions:list[str] = re.findall(rf'refs/tags/v({re.escape(series)}\.\d+{suffix})$', proc.stdout, re.M)
  if not versions: return None
  return max(versions, key=version_key)


def version_key(version:str) -> tuple[int,...]:
  m = re.fullmatch(r'(\d+\.\d+\.\d+)(?:(a|b|rc)(\d+))?', version)
  if not m: raise ValueError(f'Invalid Python version: {version!r}')
  stage = {'a': 0, 'b': 1, 'rc': 2, None: 3}[m[2]]
  return tuple(int(part) for part in m[1].split('.')) + (stage, int(m[3] or 0))


if __name__ == '__main__': main()
