# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from functools import singledispatch
from typing import Any, List, Tuple, Union

from pithy.lex import Lexer, LexMode
from pithy.parse import Choice, OneOrMore, Opt, ParseError, Parser, Struct, ZeroOrMore
from tolkien import Source, Token


class EonContainer:
  token:Token


class EonEmpty(EonContainer):
  def __init__(self, token:Token) -> None:
    self.token = token


class EonDict(EonContainer):
  def __init__(self, token:Token, items:List[Tuple[Token,'EonSyntax']]) -> None:
    self.token = token
    self.items = items


class EonList(EonContainer):
  def __init__(self, token:Token, els:List['EonSyntax']) -> None:
    self.token = token
    self.els = els


EonSyntax = Union[Token,EonContainer]


def parse_eon(path:str, text:str, generic=False) -> Any:
  '''
  Parse source text as EON data format.
  '''
  source = Source(name=path, text=text)
  syntax = eon_parser.parse('items', source)
  if generic:
    return _to_generic(syntax, source)
  else:
    return syntax


@singledispatch
def _to_generic(syntax:EonSyntax, source:Source) -> Any:
  'Convert eon AST to a generic data value.'
  raise ValueError(syntax)

@_to_generic.register
def _(syntax:Token, source:Source) -> Any:
  text = source[syntax]
  if syntax.kind == 'sym': return text
  if syntax.kind == 'str': return text
  if syntax.kind == 'int': return int(text)
  if syntax.kind == 'flt': return float(text)
  raise ValueError(syntax)

@_to_generic.register # type: ignore
def _(syntax:EonEmpty, source:Source) -> Any:
  return None

@_to_generic.register # type: ignore
def _(syntax:EonList, source:Source) -> Any:
  return [_to_generic(el, source) for el in syntax.els]

@_to_generic.register # type: ignore
def _(syntax:EonDict, source:Source) -> Any:
  return { _to_generic(k, source) : _to_generic(v, source) for (k, v) in syntax.items }



lexer = Lexer(flags='x',
  patterns=dict(
    newline = r'\n',
    spaces  = r'\ +',
    comment = r'//[^\n]*\n',

    # TODO: section labels.

    sym = r'[A-Za-z_][0-9A-Za-z_\-]*',
    flt = r'[0-9]+\.[0-9]+',
    int = r'[0-9]+',

    colon = r':',
    dash = r'-',
    tilde = r'~',
    brack_o = r'\[',
    brack_c = r'\]',
    paren_o = r'\(',
    paren_c = r'\)',
  ),
  modes=[
    LexMode('main',
      kinds=['newline', 'spaces', 'comment', 'sym', 'flt', 'int', 'colon', 'dash', 'tilde', 'brack_o', 'brack_c', 'paren_o', 'paren_c'],
      indents=True),
  ],
  transitions=[]
)


def _build_eon_parser() -> Parser:
  return Parser(lexer,
    dict(
      #sections=OneOrMore('section', drop='newline', transform=transform_sections),

      #section=Struct(Atom('section_label'), 'items'),

      key=Choice('flt', 'int', 'sym'),

      leaf=Struct(
        Choice('flt', 'int', 'sym'),
        'newline'),

      # Values always consume trailing newline.
      value=Choice('leaf', 'dash_list', 'tilde_dict'),


      dash_list=Struct(
        'dash',
        Choice('newline', 'value', transform=lambda s, t, label, val: None if label == 'newline' else val),
        Opt('list_body_multiline', dflt=()),
        transform=lambda s, t, fields: EonList(token=t, els=[fields[1], *fields[2]] if fields[1] else fields[2])),

      list_body_multiline=Struct('indent', OneOrMore('value', drop='newline'), 'dedent'),


      tilde_dict=Struct(
        'tilde',
        Choice('newline', 'kv_pair', transform=lambda s, t, label, pair: () if label == 'newline' else (pair,)),
        Opt('dict_body_multiline', dflt=()),
        transform=lambda s, t, fields: EonDict(token=t, items=[*fields[1], *fields[2]])),

      dict_body_multiline=Struct('indent', OneOrMore('kv_pair', drop='newline'), 'dedent'),

      kv_pair=Struct('key', 'colon', 'value'),

      # Items are sequences of either all list items, or all dict key-value pairs.
      # The returned value is inferred to be either a list or dict.
      items=ZeroOrMore('item', drop='newline', transform=transform_items),

      item=Choice('keylike_item', 'dash_list', 'tilde_dict', transform=transform_item),

      keylike_item=Struct('key', 'newline_or_colon_body'),

      newline_or_colon_body=Choice('newline', 'colon_body',
        transform=lambda s, t, label, val: None if label == 'newline' else val), # Newline implies that the just-parsed key is a list element.

      colon_body=Struct('colon', 'body'),

      body=Choice('value', 'body_multiline'),

      body_multiline=Struct('newline', 'indent', 'items', 'dedent'),
    ),
  literals=('newline', 'indent', 'dedent', 'colon'),
  drop=('comment', 'spaces'))


# Parser transformers.


def transform_items(source:Source, start:Token, items:List[Tuple[Any,Any]]) -> EonContainer:
  is_dict:bool
  vals:List[Any] = []
  for token, p in items:
    k, v = p
    is_pair = (v is not None) # None is never returned by value transformers, so it is a sufficient discriminator.
    if not vals:
      is_dict = is_pair
    elif is_dict != is_pair: # Inconsistent.
      if is_pair:
        msg = f'Expected list elements; received key-value pair.'
      else:
        msg = f'Expected key-value pair; received list element.'
      raise ParseError(source, token, 'inconsistent sequence. ', msg, notes=[(start, 'note: first element is here.')])
    vals.append(p if is_pair else k)
  if not vals:
    return EonEmpty(token=start)
  if is_dict:
    return EonDict(token=start, items=vals)
  else:
    return EonList(token=start, els=vals)


def transform_item(source:Source, token:Token, label:str, item:Any) -> Tuple[Token,Any]:
  if label == 'keylike_item':
    assert isinstance(item, tuple) and len(item) == 2
    return (token, item)
  else: return (token, (item, None))


eon_parser = _build_eon_parser()


def main() -> None:
  '''
  Parse specified files (or stdin) as EON and print each result.'
  '''
  from sys import argv
  from .io import outD
  from .parse import ParseError

  args = argv[1:] or ['/dev/stdin']
  for path in args:
    with open(path) as f:
      text = f.read()
    try: obj = parse_eon(path, text, generic=True)
    except ParseError as e: e.fail()
    outD(path, obj)


if __name__ == '__main__': main()
