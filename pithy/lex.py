# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Simple lexing using python regular expressions.
'''


import re
from typing import re as Re, Any, AnyStr, Iterable, Optional, Tuple


class LexError(Exception): pass


class Lexer:
  '''
  * A zero-length match, e.g. r'^' causes an exception.
    Otherwise the stream would never advance.
    One way to support zero-length tokens, e.g. r'^\s*' for Python indent tokens,
    would be to swap out the main regex for one with the pattern in question omitted,
    for the next iteration only.
  '''

  class DefinitionError(Exception): pass

  def __init__(self, flags='', invalid=None, patterns=dict(), modes=dict(), transitions=dict()):
    self.invalid = invalid

    # validate flags.
    for flag in flags:
      if flag not in 'aiLmsux':
        raise Lexer.DefinitionError(f'invalid global regex flag: {flag}')
    flags_pattern = f'(?{flags})' if flags else ''
    is_extended = 'x' in flags

    # validate patterns.
    if not patterns: raise Lexer.DefinitionError('Lexer instance must define at least one pattern')
    self.patterns = {}
    for i, (n, v) in enumerate(patterns.items()):
      if not isinstance(v, str): # TODO: also support bytes.
        raise Lexer.DefinitionError(f'member {i} {n!r} value must be a string; found {v!r}')
      pattern = f'{flags_pattern}(?P<{n}>{v})'
      try: r = re.compile(pattern) # compile each expression by itself to improve error clarity.
      except Exception as e:
        lines = [f'member {i} {n!r} pattern is invalid: {pattern}']
        if flags: lines.append(f'global flags: {flags!r}')
        if is_extended and re.search('(?<!\\)#)', v): lines.append('unescaped verbose mode comment s are  breaks lexer')
        msg = '\n  note: '.join(lines)
        raise Lexer.DefinitionError(msg) from e
      for group_name in r.groupindex:
        if group_name in patterns and group_name != n:
          raise Lexer.DefinitionError(f'member {i} {n!r} pattern contains a conflicting capture group name: {group_name!r}')
      self.patterns[n] = pattern

    # validate modes.
    self.modes = {}
    self.main = None
    if modes:
      for mode, names in modes.items():
        if not self.main: self.main = mode
        if mode in patterns:
          raise Lexer.DefinitionError(f'mode name conflicts with pattern name: {mode!r}')
        for name in names:
          if name not in patterns:
            raise Lexer.DefinitionError(f'mode {mode!r} includes nonexistant pattern: {name!r}')
        self.modes[mode] = frozenset(names)
    else:
      self.modes = { 'main' : frozenset(self.patterns) }
      self.main = 'main'
    # validate transitions.
    self.transitions = {}
    for (parent_mode, enter), (child_mode, leave) in transitions.items():
      if parent_mode not in modes: raise Lexer.DefinitionError(f'unknown parent mode: {parent_mode!r}')
      if child_mode not in modes: raise Lexer.DefinitionError(f'unknown child mode: {child_mode!r}')
      if enter not in patterns: raise Lexer.DefinitionError(f'unknown mode enter pattern: {enter!r}')
      if leave not in patterns: raise Lexer.DefinitionError(f'unknown mode leave pattern: {leave!r}')
      self.transitions[(parent_mode, enter)] = (child_mode, leave)

    choice_sep = '\n| ' if 'x' in flags else '|'
    def compile_mode(mode, pattern_names):
      return re.compile(choice_sep.join(pattern for name, pattern in self.patterns.items() if name in pattern_names))
      #^ note: iterate over self.patterns.items (not pattern_names) because the dict preserves the original pattern order.

    self.regexes = { mode : compile_mode(mode, pattern_names) for mode, pattern_names in self.modes.items() }

    self.inv_re = re.compile(f'(?s)(?P<{self.invalid}>.+)' if self.invalid else '(?s).+')


  def lex_mode(self, regex: Re.Pattern, string: AnyStr, pos=0, end: Optional[int]=None, drop: Iterable[str]=()) -> Iterable[Re.Match]:
    _pos = pos if pos >= 0 else len(string) + pos
    _end = len(string) if end is None else (end if end >= 0 else len(string) + end)
    def lex_mode_gen():
      pos = _pos
      end = _end
      def lex_inv(end):
        inv_match = self.inv_re.match(string, pos, end) # create a real match object.
        if self.invalid: return inv_match
        raise LexError(inv_match)
      while pos < end:
        match = regex.search(string, pos)
        if not match:
          yield lex_inv(end)
          break
        s, e = match.span()
        if pos < s:
          yield lex_inv(s)
        if s == e:
          raise Lexer.DefinitionError('Zero-length patterns are disallowed, because they cause the following character to be skipped.\n'
            f'  kind: {match.lastgroup}; match: {match}')
        yield match
        pos = e
    return filter((lambda token: token.lastgroup not in drop), lex_mode_gen()) if drop else lex_mode_gen()


  def lex(self, string: AnyStr, pos=0, end: Optional[int]=None, drop: Iterable[str]=()) -> Iterable[Re.Match]:
    _pos = pos if pos >= 0 else len(string) + pos
    _end = len(string) if end is None else (end if end >= 0 else len(string) + end)
    def lex_gen():
      pos = _pos
      end = _end
      stack = [(self.main, '')]
      while pos < end:
        mode, exit_name = stack[-1]
        regex = self.regexes[mode]
        for token in self.lex_mode(regex, string, pos=pos, end=end):
          pos = token.end()
          yield token
          if token.lastgroup == exit_name:
            stack.pop()
            break
          try: frame = self.transitions[(mode, token.lastgroup)]
          except KeyError: pass
          else:
            stack.append(frame)
            break
    return filter((lambda token: token.lastgroup not in drop), lex_gen()) if drop else lex_gen()


def msg_for_match(match: Re.Match, prefix: str, msg: str, pos:Optional[int]=None, end:Optional[int]=None) -> str:
  string = match.string
  p, e = match.span()
  if pos is None: pos = p
  else: assert pos >= p
  if end is None: end = e
  else: assert end <= e
  line_num = string.count('\n', 0, pos) # number of newlines preceeding pos.
  line_start = string.rfind('\n', 0, pos) + 1 # rfind returns -1 for no match, happens to work perfectly.
  line_end = string.find('\n', pos)
  if line_end == -1: line_end = len(string)
  line = string[line_start:line_end]
  col = pos - line_start
  indent = ' ' * col
  underline = '~' * (min(end - pos, len(line))) or '^'
  return f'{prefix}:{line_num+1}:{col+1}: {msg}\n{line}\n{indent}{underline}'


def line_col_0_for_match(match: Re.Match) -> Tuple[int, int]:
  pos = match.start()
  line_num = string.count('\n', 0, pos) # number of newlines preceeding pos.
  line_start = string.rfind('\n', 0, pos) + 1 # rfind returns -1 for no match, happens to work perfectly.
  return (line_num, pos - line_start)
