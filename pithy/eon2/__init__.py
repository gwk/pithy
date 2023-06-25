# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Eon is a structured data format, similar to JSON and YAML.
'''


from typing import Any, TypeVar

from tolkien import Source, Token

from ..parse import ParseError
from .convert import convert_eon
from .parse import eon_parser


_T = TypeVar('_T')


def _str_token_val(source:Source, token:Token) -> str:
  k = token.kind
  t = source[token]
  if k == 'esc_char': return _esc_char_vals[t]
  else: return t


_esc_char_vals = {
  '\\n' : '\n',
  '\\\\' : '\\',
  '\\"' : '"',
  "\\'" : "'",
}


def parse_eon(path:str, text:str, to:type[_T]) -> Any:
  '''
  Parse source text as EON data format.
  '''
  source = Source(name=path, text=text)
  syntax = eon_parser.parse('body', source)
  return convert_eon(syntax, source, to)


def parse_eon_or_fail(path:str, text:str, to:type[_T]) -> Any:
  try: return parse_eon(path, text, to)
  except ParseError as e: e.fail()
