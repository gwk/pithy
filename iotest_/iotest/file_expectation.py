# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from itertools import zip_longest
from typing import Callable, Pattern

from pithy.io import read_from_path


class TestCaseError(Exception): pass


class FileExpectation:

  def __init__(self, path:str, info:dict[str,str], expand_str_fn:Callable):
    if path.find('..') != -1:
      raise TestCaseError(f"file expectation {path}: cannot contain '..'")
    self.path = expand_str_fn(path)
    self.mode = info.get('mode', 'equal')
    validate_exp_mode(path, self.mode)
    try:
      exp_path = info['path']
    except KeyError:
      val = info.get('val', '')
    else:
      if 'val' in info:
        raise TestCaseError(f'file expectation {path}: cannot specify both `path` and `val` properties')
      exp_path_expanded = expand_str_fn(exp_path)
      val = read_from_path(exp_path_expanded)
    self.val = expand_str_fn(val)
    self.src_path = info.get('path') # Do not yet have capability to update the value within an iot file.
    if self.mode == 'match':
      self.match_pattern_pairs = self.compile_match_lines(self.val)
    else:
      self.match_pattern_pairs = []
    self.match_error: tuple[int,Pattern|None,str]|None = None


  def compile_match_lines(self, text:str) -> list[tuple[str,Pattern]]:
    return [self.compile_match_line(i, line) for i, line in enumerate(text.splitlines(True), 1)]


  def compile_match_line(self, i:int, line:str) -> tuple[str, Pattern]:
    prefix = line[:2]
    contents = line[2:]
    valid_prefixes = ('|', '|\n', '| ', '~', '~\n', '~ ')
    if prefix not in valid_prefixes:
      raise TestCaseError("test expectation: {!r};\nmatch line {}: must begin with one of: {}\n{!r}".format(
        self.path, i, ', '.join(repr(p) for p in valid_prefixes), line))
    if prefix.endswith('\n'):
      # these two cases exist to be lenient about empty lines,
      # where otherwise the pattern line would consist of the symbol and a single space.
      # since trailing space is highlighted by `git diff` and often considered bad style,
      # we allow it to be omitted, since there is no loss of generality for the patterns.
      contents = '\n'
    try:
      return (line, re.compile(contents if prefix == '~ ' else re.escape(contents)))
    except Exception as e:
      raise TestCaseError('test expectation: {!r};\nmatch line {}: pattern is invalid regex:\n{!r}\n{}'.format(
        self.path, i, contents, e)) from e


  def __repr__(self) -> str:
    val_repr = repr(self.val) if len(self.val) < 64 else repr(self.val[:64]) + '…'
    return f'FileExpectation({self.path!r}, {self.mode!r}, {val_repr})'.format(self.path, self.mode, self.val)



def validate_exp_mode(key:str, mode:str) -> None:
  if mode not in file_expectation_fns:
    raise TestCaseError(f'key: {key}: invalid file expectation mode: {mode}')


# file expectation functions.

def compare_equal(exp:FileExpectation, val:str) -> bool:
  return exp.val == val # type: ignore[no-any-return]


def compare_contain(exp:FileExpectation, val:str) -> bool:
  return val.find(exp.val) != -1


def compare_match(exp:FileExpectation, val:str) -> bool:
  lines: list[str] = val.splitlines(True)
  for i, (pair, line) in enumerate(zip_longest(exp.match_pattern_pairs, lines), 1):
    if pair is None:
      exp.match_error = (i, None, line)
      return False
    (pattern, regex) = pair
    if line is None or not regex.fullmatch(line):
      exp.match_error = (i, pattern, line) # type: ignore[assignment]
      return False
  return True


def compare_ignore(exp:FileExpectation, val:str) -> bool:
  return True


file_expectation_fns = {
  'equal'   : compare_equal,
  'contain' : compare_contain,
  'match'   : compare_match,
  'ignore'  : compare_ignore,
}
