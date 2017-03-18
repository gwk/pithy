# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Simple lexing.
Subclass Lexer and Enum to create a concrete lexer.

| class Numbers(Lexer, Enum):
|   Line = r'\n'
|   Space = r' +'
|   Num = r'\d+'

Caveats:
* If one pattern specifies a global flag, e.g. `(?x)`, all patterns are affected.
  Python 3.6 supports localized flag, e.g. `(?x: ...)`.
* A rule that matches zero-length strings, e.g. r'^' is defined to raise an exception.
  Otherwise it would match but the character immediately following would be skipped.
  This is the behavior of the underlying finditer,
  and there does not appear to be a way to advance without using multiple regexes.
'''

import re
from enum import Enum
from typing import Any, AnyStr, Iterable, re as Re, Tuple


class LexError(Exception): pass

class LexDefinitionError(Exception): pass

inv_re = re.compile(r'(?s).+') # used to match all characters that did not otherwise match.


class Lexer:

  _regex = None
  _inv_member = None


  @classmethod
  def _compile(cls):
    members = tuple(cls.__members__.values())
    for i, m in enumerate(members):
      n = m._name_
      v = m._value_
      if v is None:
        if i: raise LexDefinitionError(f'member {i} {n!r} value is None (only member 0 may be signify the invalid token)')
        continue
      if not isinstance(v, str):
        raise LexDefinitionError(f'member {i} {n!r} value must be a string; found {v!r}')
      try: r = re.compile(v) # compile each expression by itself to improve error clarity.
      except Exception as e: raise LexDefinitionError(f'member {i} {n!r} pattern is invalid: {v}') from e
      for group_name in r.groupindex:
        if group_name in cls.__members__:
          raise LexDefinitionError(f'member {i} {n!r} pattern contains a conflicting capture group name: {group_name!r}')
    if members and members[0]._value_ is None: # first member represents invalid token.
      cls._inv_member = members[0]
      pattern_members = members[1:]
    else: # no invalid token; will raise on invalid input.
      cls._inv_member = None
      pattern_members = members
    if not pattern_members: raise LexDefinitionError('Lexer subclass must define at least one member')
    pattern = '|'.join(f'(?P<{m._name_}>{m._value_})' for m in pattern_members)
    cls._regex = re.compile(pattern)


  @classmethod
  def lex(cls, string: AnyStr, drop: Iterable[Any]=()) -> Iterable[Tuple['Lexer', Re.Match]]:
    if not cls._regex: cls._compile()
    def lex_gen():
      drop_inv = (cls._inv_member in drop)
      prev_end = 0
      def lex_inv(pos):
        inv_match = inv_re.match(string, prev_end, pos) # create a real match object.
        if cls._inv_member:
          return None if drop_inv else (cls._inv_member, inv_match)
        raise LexError(inv_match)
      for match in cls._regex.finditer(string):
        start, end = match.span()
        if prev_end < start: yield lex_inv(start)
        if start == end:
          raise LexDefinitionError('Zero-length patterns are disallowed, because they cause the following character to be skipped.')
        kind = cls.__members__[match.lastgroup]
        yield None if kind in drop else (kind, match)
        prev_end = end
      if prev_end < len(string): yield lex_inv(len(string))
    return filter(None, lex_gen()) if drop else lex_gen()
