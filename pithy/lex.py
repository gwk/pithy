# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Simple lexing using python regular expressions.
'''


import re
from typing import re as Re, Any, AnyStr, Iterable, Optional, Tuple


class LexError(Exception): pass




class Lexer:
  '''
  Caveats:
  * If one pattern specifies a global flag, e.g. `(?x)`, all patterns are affected.
    Python 3.6 supports localized flag, e.g. `(?x: ...)`.
  * A rule that matches zero-length strings, e.g. r'^' is defined to raise an exception.
    Otherwise it would match but the character immediately following would be skipped.
    This is the behavior of the underlying finditer.
    One way to support zero-length tokens, e.g. r'^\s*' for Python indent tokens,
    would be to swap out the main regex for one with the pattern in question omitted,
    for the next iteration only.
  '''

  class DefinitionError(Exception): pass

  def __init__(self, _lexer_global_flags='', **members):
    for flag in _lexer_global_flags:
      if flag not in 'aiLmsux':
        raise Lexer.DefinitionError(f'invalid global regex flag: {flag}')
    flags_pattern = f'(?{_lexer_global_flags})' if _lexer_global_flags else ''
    is_extended = 'x' in _lexer_global_flags
    self.members = members
    self.inv_name = None
    patterns = []
    for i, (n, v) in enumerate(members.items()):
      if v is None:
        if i: raise Lexer.DefinitionError(f'member {i} {n!r} value is None (only the first member may be None, to signify the invalid token)')
        self.inv_name = n
        continue
      if not isinstance(v, str): # TODO: also support bytes.
        raise Lexer.DefinitionError(f'member {i} {n!r} value must be a string; found {v!r}')
      pattern = f'{flags_pattern}(?P<{n}>{v})'
      try: r = re.compile(pattern) # compile each expression by itself to improve error clarity.
      except Exception as e:
        lines = [f'member {i} {n!r} pattern is invalid: {pattern}']
        if _lexer_global_flags: lines.append(f'global flags: {_lexer_global_flags!r}')
        if is_extended and re.search('(?<!\\)#)', v): lines.append('unescaped verbose mode comment s are  breaks lexer')
        msg = '\n  note: '.join(lines)
        raise Lexer.DefinitionError(msg) from e
      for group_name in r.groupindex:
        if group_name in members and group_name != n:
          raise Lexer.DefinitionError(f'member {i} {n!r} pattern contains a conflicting capture group name: {group_name!r}')
      patterns.append(pattern)
    if not patterns: raise Lexer.DefinitionError('Lexer instance must define at least one pattern')
    choice_sep = '\n| ' if 'x' in _lexer_global_flags else '|'
    pattern = choice_sep.join(patterns)
    self.regex = re.compile(pattern)
    self.inv_re = re.compile(f'(?s)(?P<{self.inv_name}>.+)' if self.inv_name else '(?s).+')


  def lex(self, string: AnyStr, pos=0, end: Optional[int]=None, drop: Iterable[str]=()) -> Iterable[Re.Match]:
    _pos = pos if pos >= 0 else len(string) + pos
    _end = len(string) if end is None else (end if end >= 0 else len(string) + end)
    def lex_gen():
      drop_inv = (self.inv_name in drop)
      pos = _pos
      end = _end
      def lex_inv(end):
        inv_match = self.inv_re.match(string, pos, end) # create a real match object.
        if self.inv_name:
          return None if drop_inv else inv_match
        raise LexError(inv_match)
      while pos < end:
        match = self.regex.search(string, pos)
        if not match:
          yield lex_inv(end)
          break
        s, e = match.span()
        if pos < s:
          yield lex_inv(s)
        if s == e:
          raise Lexer.DefinitionError('Zero-length patterns are disallowed, because they cause the following character to be skipped.')
        yield None if (match.lastgroup in drop) else match
        pos = e
    return filter(None, lex_gen()) if drop else lex_gen()


class ModeLexer:

  class DefinitionError(Exception): pass

  def __init__(self, *lexers: Lexer, **transitions: str):
    if not lexers: raise ModeLexer.DefinitionError('ModeLexer instance requires at least one Lexer')
    self.lexers = lexers
    names_to_lexers = {}
    for lexer in lexers:
      for name in lexer.members:
        if name in names_to_lexers:
          raise ModeLexer.DefinitionError(f'duplicate member name: {name}')
        names_to_lexers[name] = lexer
    self.transitions = {}
    for entry_name, exit_name in transitions.items():
      if entry_name not in names_to_lexers:
        raise ModeLexer.DefinitionError(f'transition entry name does not match any member: {entry_name}')
      if exit_name not in names_to_lexers:
        raise ModeLexer.DefinitionError(f'transition exit name does not match any member: {exit_name}')
      self.transitions[entry_name] = (names_to_lexers[exit_name], exit_name)


  def lex(self, string: AnyStr, pos=0, end: Optional[int]=None, drop: Iterable[str]=()) -> Iterable[Re.Match]:
    pos = pos if pos >= 0 else len(string) + pos
    end = len(string) if end is None else (end if end >= 0 else len(string) + end)
    stack = [(self.lexers[0], None)]
    while pos < end:
      lexer, exit_name = stack[-1]
      for token in lexer.lex(string, pos=pos, end=end, drop=drop):
        pos = token.end()
        yield token
        if token.lastgroup == exit_name:
          stack.pop()
          break
        try: sub = self.transitions[token.lastgroup]
        except KeyError: pass
        else:
          stack.append(sub)
          break


def msg_for_match(match: Re.Match, prefix: str, msg: str) -> str:
  string = match.string
  pos, end = match.span()
  line_num = string.count('\n', 0, pos) # number of newlines preceeding pos.
  line_start = string.rfind('\n', 0, pos) + 1 # rfind returns -1 for no match, happens to work perfectly.
  line_end = string.find('\n', pos)
  if line_end == -1: line_end = len(string)
  line = string[line_start:line_end]
  col = pos - line_start
  indent = ' ' * col
  underline = '~' * (min(end - pos, len(line))) or '^'
  return f'{prefix}:{line_num+1}:{col+1}: {msg}\n{line}\n{indent}{underline}'
