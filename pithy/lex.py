# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Simple lexing using python regular expressions.
'''


import re
from typing import Any, AnyStr, Iterable, re as Re, Tuple


class LexError(Exception): pass

class LexDefinitionError(Exception): pass



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

  def __init__(self, **members):
    self.members = members
    self.inv_name = None
    patterns = []
    for i, (n, v) in enumerate(members.items()):
      if v is None:
        if i: raise LexDefinitionError(f'member {i} {n!r} value is None (only the first member may be None, to signify the invalid token)')
        self.inv_name = n
        continue
      if not isinstance(v, str): # TODO: also support bytes.
        raise LexDefinitionError(f'member {i} {n!r} value must be a string; found {v!r}')
      try: r = re.compile(v) # compile each expression by itself to improve error clarity.
      except Exception as e: raise LexDefinitionError(f'member {i} {n!r} pattern is invalid: {v}') from e
      for group_name in r.groupindex:
        if group_name in members:
          raise LexDefinitionError(f'member {i} {n!r} pattern contains a conflicting capture group name: {group_name!r}')
      patterns.append((n, v))
    if not patterns: raise LexDefinitionError('Lexer instance must define at least one pattern')
    pattern = '|'.join(f'(?P<{n}>{v})' for n, v in patterns)
    self.regex = re.compile(pattern)
    self.inv_re = re.compile(f'(?s)(?P<{self.inv_name}>.+)' if self.inv_name else '(?s).+')


  def lex(self, string: AnyStr, drop: Iterable[str]=()) -> Iterable[Re.Match]:
    def lex_gen():
      drop_inv = (self.inv_name in drop)
      prev_end = 0
      def lex_inv(pos):
        inv_match = self.inv_re.match(string, prev_end, pos) # create a real match object.
        if self.inv_name:
          return None if drop_inv else inv_match
        raise LexError(inv_match)
      while prev_end < len(string):
        match = self.regex.search(string, prev_end)
        if not match:
          yield lex_inv(len(string))
          break
        start, end = match.span()
        if prev_end < start:
          yield lex_inv(start)
        if start == end:
          raise LexDefinitionError('Zero-length patterns are disallowed, because they cause the following character to be skipped.')
        yield None if (match.lastgroup in drop) else match
        prev_end = end
    return filter(None, lex_gen()) if drop else lex_gen()


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
