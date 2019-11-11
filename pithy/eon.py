# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from functools import singledispatch
from itertools import chain
from typing import Container, DefaultDict, Dict, FrozenSet, List, Match, NoReturn, Optional, Set, Tuple, Type, cast

from pithy.io import *
from pithy.iterable import OnHeadless, fan_by_key_fn, group_by_heads
from pithy.lex import Lexer, LexMode, LexTrans
from pithy.parse import Choice, OneOrMore, Opt, ParseError, Parser, Struct, ZeroOrMore
from pithy.string import clip_prefix
from pithy.unicode import CodeRange, CodeRanges, codes_for_ranges
from pithy.unicode.charsets import unicode_charsets
from tolkien import Source, Token


def parse_eon(path:str, text:str, generic=False) -> Any:
  '''
  Parse source text as EON data format.
  '''
  source = Source(name=path, text=text)
  items = eon_parser.parse('items', source)
  if generic:
    return _to_generic(items, source)
  else:
    return items


@singledispatch
def _to_generic(items:List[Any], source:Source) -> Any:
  'Convert eon AST to a generic data value.'
  raise ValueError(items)

@_to_generic.register
def _(ast:Token, source:Source) -> Any:
  text = source[ast]
  if ast.kind == 'sym': return text
  if ast.kind == 'str': return text
  if ast.kind == 'int': return int(text)
  if ast.kind == 'flt': return float(text)
  raise ValueError(ast)

@_to_generic.register # type: ignore
def _(ast:tuple, source:Source) -> Any:
  return tuple(_to_generic(el, source) for el in ast)

@_to_generic.register # type: ignore
def _(ast:list, source:Source) -> Any:
  return [_to_generic(el, source) for el in ast]

@_to_generic.register # type: ignore
def _(ast:dict, source:Source) -> Any:
  return { _to_generic(k, source) : _to_generic(v, source) for (k, v) in ast.items() }



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
        Choice('newline', 'value', transform=lambda s, label, val: None if label == 'newline' else val),
        Opt('list_body_multiline', dflt=()),
        transform=lambda s, fields: [fields[1], *fields[2]] if fields[1] else fields[2]),

      list_body_multiline=Struct('indent', OneOrMore('value', drop='newline'), 'dedent'),


      tilde_dict=Struct(
        'tilde',
        Choice('newline', 'kv_pair', transform=lambda s, label, pair: () if label == 'newline' else (pair,)),
        Opt('dict_body_multiline', dflt=()),
        transform=lambda s, fields: dict(chain(fields[1], fields[2]))),

      dict_body_multiline=Struct('indent', OneOrMore('kv_pair', drop='newline'), 'dedent'),

      kv_pair=Struct('key', 'colon', 'value'),

      # Items are sequences of either all list items, or all dict key-value pairs.
      # The returned value is inferred to be either a list or dict.
      items=ZeroOrMore('item', drop='newline', transform=transform_items),

      item=Choice('keylike_item', 'dash_list', 'tilde_dict', transform=transform_item),

      keylike_item=Struct('key', 'newline_or_colon_body'),

      newline_or_colon_body=Choice('newline', 'colon_body',
        transform=lambda s, label, val: None if label == 'newline' else val), # Newline implies that the just-parsed key is a list element.

      colon_body=Struct('colon', 'body'),

      body=Choice('value', 'body_multiline'),

      body_multiline=Struct('newline', 'indent', 'items', 'dedent'),
    ),
  literals=('newline', 'indent', 'dedent', 'colon'),
  drop=('comment', 'spaces'))


# Parser transformers.


def transform_items(source:Source, items:List[Tuple[Any,Any]]) -> Any:
  is_dict:Optional[bool] = None
  first_k = None
  for k, v in items:
    is_pair = (v is not None) # None is never returned by value transformers, so it is a sufficient discriminator.
    if is_dict is None:
      is_dict = is_pair
      first_k = k
    elif is_dict != is_pair: # Inconsistent.
      token = k
      while not isinstance(token, Token): token = token[0] # Extract leading token from a structure key.
      if is_pair:
        msg = f'Expected list elements; received key-value pair.'
      else:
        msg = f'Expected key-value pair; received list element.'
      assert first_k is not None
      first_token = first_k
      while not isinstance(first_token, Token): first_token = first_token[0] # Extract leading token from a structure key.
      raise ParseError(source, token, 'inconsistent sequence. ', msg, notes=[(first_token, 'note: first element is here.')])
  if is_dict is None: # Default to dict; if caller is expecting a simple iterable, this still works.
    return {}
  if is_dict:
    return dict(items)
  else:
    return [item[0] for item in items]


def transform_item(source:Source, label:str, item:Any) -> Any:
  if label == 'keylike_item':
    assert isinstance(item, tuple) and len(item) == 2
    return item
  else: return (item, None)


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
