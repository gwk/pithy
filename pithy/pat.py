# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import environ
from sys import stderr
from typing import Iterable
from .path import path_dir, path_join


class ParseError(Exception): pass

def pat_dependency(src_path:str, src_lines:Iterable[str]) -> str:
  '''
  Return a list of dependencies.
  A .pat file always has a single dependency: the source file it patches.
  '''
  it = iter(src_lines)
  version_line = next(it, '')
  if not version_line.startswith('pat v'):
    raise ParseError(f'pat error: {src_path}:1:1: malformed version string.')
  orig_line = next(it, '')
  orig_path = orig_line.strip()
  if not orig_path:
    raise ParseError(f'pat error: {src_path}:2:1: line specifying original path is missing or empty.')
  return orig_path
