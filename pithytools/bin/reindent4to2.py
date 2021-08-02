#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# Reindent a text file from four spaces to two.

import sys
import random
from typing import TextIO

from pithy.fs import path_exists, is_file, move_file
from pithy.io import errL, outL


def main() -> None:

  for path in sys.argv[1:]:
    try:
      outL(path)
      reindent(path)
    except PassableException as e:
      errL(f'error: {path}: {e}')
      continue


def reindent(path: str) -> None:
  if not path_exists(path, follow=False): raise PassableException('path does not exist.')
  if not is_file(path, follow=False): raise PassableException('path is not a file.')

  reindent_path = path + '.reindent'
  orig_path = path + '.orig'
  #if path_exists(reindent_path, follow=False): raise PassableException(f'temporary path already exists: {reindent_path!r}')
  #if path_exists(orig_path, follow=False): raise PassableException(f'temporary path already exists: {orig_path!r}')

  is_perfect = True
  with open(path, 'r') as f_in, open(reindent_path, 'w') as f_out:
    for line_idx, line in enumerate(f_in):
      is_perfect &= reindent_line(path, f_out, line_idx, line)

  #move_file(path=path, to=orig_path)
  #move_file(path=reindent_path, to=path)


def reindent_line(path: str, f_out: TextIO, line_idx: int, line: str) -> bool:
  i = 0 # Current position.
  spaces = 0 # Number of spaces since last indent counted.
  indents = 0 # Number of indents counted.
  while i < len(line):
    c = line[i]
    if c == '\t':
      spaces = 0 # Any odd spaces are lumped in with the tab.
      indents += 1
    elif c == ' ':
      spaces += 1
      if spaces == 4:
        spaces = 0
        indents += 1
    else: break
    i += 1

  if spaces:
    s = '' if spaces == 1 else 's'
    errL(f'{path}:{line_idx+1}: note: {spaces} extra space{s}:\n{line.rstrip()}')

  replacement = '  ' * indents + line[i:]
  f_out.write(replacement)

  is_perfect = (spaces == 0)
  return is_perfect


class PassableException(Exception):
  'An exception regarding input for which we can safely continue.'


if __name__ == '__main__': main()
