# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Simple lexing.
Subclass Lexer and Enum to create a concrete lexer.

| class Numbers(Lexer, Enum):
|   Line = r'\n'
|   Space = r' +'
|   Num = r'\d+'

Caveats:
* If one pattern specifies a flag, all patterns are affected.
  * maybe require all flags at the beginning?
  * or hack in a @setFlags decorator or class function?
'''

import re
from enum import Enum
from typing import AnyStr, Iterable, re as Re, Tuple


class LexError(Exception): pass

class LexDefinitionError(Exception): pass

inv_re = re.compile(r'.+') # used to match all characters that did not otherwise match.


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
    pattern = '|'.join(f'(?P<{m._name_}>{m._value_})' for m in pattern_members)
    cls._regex = re.compile(pattern)


  @classmethod
  def lex(cls, string: AnyStr) -> Iterable[Tuple['Lexer', Re.Match]]:
    if not cls._regex: cls._compile()
    def lex_gen():
      prev_end = 0
      def lex_inv(pos):
        inv_match = inv_re.match(string, prev_end, pos) # create a real match object.
        assert inv_match is not None
        if cls._inv_member: return (cls._inv_member, inv_match)
        else: raise LexError(inv_match)
      for match in cls._regex.finditer(string):
        if prev_end < match.start(): yield lex_inv(match.start())
        yield (cls.__members__[match.lastgroup], match)
        prev_end = match.end()
      if prev_end < len(string): yield lex_inv(len(string))
    return lex_gen()
