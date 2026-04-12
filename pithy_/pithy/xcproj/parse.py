# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pprint import pformat
from typing import Any, Dict

from pithy.buffer import Buffer
from pithy.io import errL
from pithy.lex import Lexer
from tolkien import Source, Token

from .pbx import DefError, node_classes, PlistRoot
from .util import unquote_string


lexer = Lexer(patterns=dict(
  utf8_header = r'// !\$\*UTF8\*\$!',
  newline     = r'\n',
  comment     = r'/\*([^\n\*]|\*[^\n/])*\*/',
  spaces      =  r'\ +',
  tabs        = r'\t+',
  sym         = r'[\w\./]+', # note: duplicated in quote_string below.
  string      = r'"([^\\\n"]|\\"|\\\\|\\n)*"', # Rule structure is: Q([^EQ]|EQ|EE)*Q.
  braceO      = r'\{',
  braceC      = r'\}',
  parenO      = r'\(',
  parenC      = r'\)',
  comma       = r',',
  semicolon   = r';',
  eq          = r'=',
))


def parse_pbx(path:str, text:str) -> Any:
  source = Source(name=path, text=text)
  buffer = Buffer(lexer.lex(source, drop={'newline', 'comment', 'spaces', 'tabs'}))
  try:
    expect(buffer, 'utf8_header')
    head = expect(buffer, 'braceO')
    return parse_obj(source, buffer, head, is_root=True)
  except ParseError as e:
    source.fail((e.token, f'error: {e}.'))
  except DefError as e:
    source.fail((e.token, f'error: {e}.\n{pformat(e.dictionary)}'))


def parse(source:Source, buffer:Buffer[Token]) -> Any:
  token = next(buffer)
  kind = token.kind
  if kind == 'sym':
    return source[token]
  if kind == 'string':
    return unquote_string(source[token])
  if kind == 'braceO':
    return parse_obj(source, buffer, token)
  if kind == 'parenO':
    return parse_list(source, buffer, token)
  else:
    raise ParseError(token, f'unexpected token: {token.kind}')


def parse_obj(source:Source, buffer:Buffer[Token], head:Token, is_root:bool=False) -> Any:
  d:Dict[str,Any] = {}
  while True:
    token = next(buffer)
    kind = token.kind
    if kind == 'braceC': break
    if kind == 'sym':
      k = source[token]
    elif kind == 'string':
      k = unquote_string(source[token])
    else:
      raise ParseError(token, f'expected object key to be a symbol; received {kind}')
    if k in d: raise ParseError(token, f'duplicate object key: {k!r}')
    expect(buffer, 'eq')
    v = parse(source, buffer)
    d[k] = v
    expect(buffer, 'semicolon')

  if is_root: return PlistRoot(**d)

  try: isa = d['isa']
  except KeyError: return d
  try: pbx_class = node_classes[isa]
  except KeyError as e:
    fields = '\n'.join([f'  {k}: {type(v).__name__}' for k, v in d.items() if k != 'isa'])
    errL(f'unknown PBX class; approximate implementation:\n\nclass {isa}(PBX):\n{fields}\n')
    raise DefError(head, d, f'unknown PBX class: {isa}') from e
  return pbx_class(head, **d)


def parse_list(source:Source, buffer:Buffer[Token], head:Token) -> Any:
  l = []
  while buffer.peek().kind != 'parenC':
    l.append(parse(source, buffer))
    expect(buffer, 'comma')
  next(buffer)
  return l


def expect(buffer:Buffer[Token], kind:str) -> Token:
  token = next(buffer)
  if token.kind == kind: return token
  raise ParseError(token, f'expected {kind}')


class ParseError(Exception):
  def __init__(self, token:Token, msg:str) -> None:
    super().__init__(msg)
    self.token = token
