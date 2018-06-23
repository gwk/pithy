# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import stderr
from typing import Any, NoReturn, TextIO


def pat_dependency(src_path: str, src_file: TextIO) -> str:
  '''
  Return a list of dependencies.
  A .pat file always has a single dependency: the source file it patches.
  '''
  version_line = src_file.readline()
  orig_line = src_file.readline()
  orig_path = orig_line.strip()
  if not orig_path:
    failF('pat error: {}:2:1: line specifying original path is missing or empty.', src_path)
  return orig_path


def errF(fmt: str, *items: Any) -> None:
  print(fmt.format(*items), end='', file=stderr)

def errFL(fmt: str, *items: Any) -> None:
  print(fmt.format(*items), file=stderr)

def failF(fmt: str, *items: Any) -> NoReturn:
  errFL('pat error: ' + fmt, *items)
  exit(1)
