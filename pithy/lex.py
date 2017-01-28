# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Simple lexing.
* Allow first variant to be Invalid. Required?
* If one pattern specifies a flag, all patterns are affected; maybe require all flags at the beginning?'
* or hack in a @setFlags decorator or class function?
'''

import re
from enum import Enum
from typing import AnyStr, Iterable, re as Re


class LexError(Exception): pass

class LexUnescapedParenError(Exception): pass

_unescaped_paren_re = re.compile(r'(?!\\)\((?!\?)')


class Lexer:

  _index = None
  _regex = None

  @classmethod
  def lex(cls, string: AnyStr) -> Iterable[AnyStr]:
    if not cls._index:
      cls._index = (None,) + tuple(cls.__members__.values())
      for member in cls.__members__.values():
        if _unescaped_paren_re.search(member._value_):
          raise LexUnescapedParenError(member._value_)
      pattern = '|'.join(f'({m._value_})' for m in cls.__members__.values())
      cls._regex = re.compile(pattern)

    def lex_gen():
      prev = None
      for match in cls._regex.finditer(string):
        if prev and prev.end() != match.start():
          raise LexError(string, prev.end())
        yield (cls._index[match.lastindex], match.group())

    return lex_gen()
