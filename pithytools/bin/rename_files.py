# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from argparse import ArgumentParser

from pithy.fs import move_file
from pithy.io import confirm


def main() -> None:

  parser = ArgumentParser(description='Rename files.')
  parser.add_argument('paths', nargs='+', help='Paths to rename.')
  parser.add_argument('-pattern', required=True, help='Regex pattern to match.')
  parser.add_argument('-sub', required=True, help='Substitution string (Python re.sub syntax).')
  parser.add_argument('-yes', action='store_true', help='Apply changes; otherwise, show what will be done and confirm.')
  parser.add_argument('-overwrite', action='store_true', help='Allow overwriting existing files.')
  parser.add_argument('-create-dirs', action='store_true', help='Create parent directories for new paths as needed.')

  args = parser.parse_args()

  try: pattern = re.compile(args.pattern)
  except re.error as e: exit(f'Invalid regex pattern {args.pattern}: {e}')
  sub = args.sub
  print('pattern:', pattern.pattern)
  print('sub:', sub)

  renames:list[tuple[str,str]] = []

  for path in args.paths:
    m = pattern.search(path)
    if not m:
      print(f'{path}: no match.')
      continue
    new_path = pattern.sub(sub, path, count=1)
    if new_path == path:
      print(f'{path}: no change.')
      continue
    print(f'{path} -> {new_path}')
    renames.append((path, new_path))

  if not (args.yes or confirm(f'Rename {len(renames)} files?')):
    exit(1)

  for src, dst in renames:
    try: move_file(src, dst, overwrite=args.overwrite, create_dirs=args.create_dirs)
    except OSError as e: print(f'Error renaming {src} to {dst}: {e}')
