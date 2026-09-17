#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Check the version, imports and console entry points of an installed package.'

import sys
from importlib import import_module
from importlib.metadata import distribution


def main() -> None:
  if len(sys.argv) < 3:
    sys.exit(f'usage: {sys.argv[0]} package version [extra-import ...]')
  package, version, *extra_imports = sys.argv[1:]
  dist = distribution(package)
  if dist.version != version:
    sys.exit(f'Expected {package} {version}; installed {dist.version}.')
  failures = []
  for name in [package, *extra_imports]:
    try: import_module(name)
    except Exception as e: failures.append(f'{name}: {type(e).__name__}: {e}')
  entry_points = [ep for ep in dist.entry_points if ep.group == 'console_scripts']
  for ep in entry_points:
    try: ep.load()
    except Exception as e: failures.append(f'{ep.name} ({ep.value}): {type(e).__name__}: {e}')
  if failures: sys.exit('\n'.join(failures))
  print(f'Validated {package} {dist.version}: package imports and {len(entry_points)} console entry points load.')


if __name__ == '__main__': main()
