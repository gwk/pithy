# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Eon is a a structured data format, similar to JSON and YAML.
'''


import re
from collections.abc import Mapping
from functools import singledispatch
from inspect import Parameter, signature
from typing import (Any, Callable, Dict, get_args as get_type_args, get_origin, get_type_hints, Iterable, Iterator, List,
  Optional, Type, TypeVar, Union)

from tolkien import HasSlc, slc_str, Source, Token

from .lex import Lexer, LexMode, LexTrans
from .parse import Choice, OneOrMore, Opt, ParseError, Parser, Struct, ZeroOrMore, choice_val
from .util import memoize


_T = TypeVar('_T')


class EonContainer:
  slc:slice

  @property
  def slc_str(self) -> str: return slc_str(self.slc)

EonSyntax = Union[Token,EonContainer]


class EonEmpty(EonContainer):
  def __init__(self, slc:slice):
    self.slc = slc

  def __repr__(self) -> str: return f'{type(self).__name__}({self.slc_str})'


class EonDict(EonContainer):
  def __init__(self, slc:slice, items:List[tuple[Token,'EonSyntax']]):
    self.slc = slc
    self.items = items

  def __repr__(self) -> str: return f'{type(self).__name__}({self.slc_str}, <{len(self.items)} items>)'

  def __iter__(self) -> Iterator[tuple[Token,EonSyntax]]: return iter(self.items)


class EonList(EonContainer):
  def __init__(self, slc:slice, els:List['EonSyntax']):
    self.slc = slc
    self.els = els

  def __repr__(self) -> str: return f'{type(self).__name__}({self.slc_str}, <{len(self.els)} els>)'

  def __iter__(self) -> Iterator[EonSyntax]: return iter(self.els)


class EonStr(EonContainer, HasSlc):
  def __init__(self, slc:slice, tokens:List[Token]):
    self.slc = slc
    self.tokens = tokens

  def __repr__(self) -> str: return f'{type(self).__name__}({self.slc_str}, <{len(self.tokens)} tokens>)'

  def __iter__(self) -> Iterator[EonSyntax]: return iter(self.tokens)

  def value(self, source:Source) -> str:
    return ''.join(source[t] for t in self.tokens)


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


class ConversionError(ParseError):
  error_prefix = 'conversion'


def parse_eon(path:str, text:str, to:Type[_T]) -> Any:
  '''
  Parse source text as EON data format.
  '''
  source = Source(name=path, text=text)
  syntax = eon_parser.parse('items', source)
  return convert_eon(syntax, source, to)


def parse_eon_or_fail(path:str, text:str, to:Type[_T]) -> Any:
  try: return parse_eon(path, text, to)
  except ParseError as e: e.fail()


@singledispatch
def convert_eon(syntax:EonSyntax, source:Source, to:Type[_T]) -> Any: # TODO: this should return _T but mypy doesn't understand.
  'Convert eon AST to a generic data value.'
  raise NotImplementedError(f'unimplemented syntax type: {syntax}')


@convert_eon.register
def convert_eon_token(syntax:Token, source:Source, to:Type[_T]) -> _T:
  text = source[syntax]
  if to is str: return text # type: ignore[return-value] # TODO: handle quoted strings.
  if to is bool: return _bool_vals[text] # type: ignore[return-value]
  if to in (Any, object):
    if syntax.kind == 'sym': return text # type: ignore[return-value]
    if syntax.kind == 'int': return int(text) # type: ignore[return-value]
    if syntax.kind == 'flt': return float(text) # type: ignore[return-value]
    raise NotImplementedError(syntax)
  rtt = get_origin(to) or to
  try: return rtt(text) # type: ignore[call-arg]
  except Exception as e:
    raise ConversionError(source, syntax, f'expected {_fmt_type(to)}; received {syntax.kind}.\n{_fmt_exc(e)}') from e


@convert_eon.register
def convert_eon_str(syntax:EonStr, source:Source, to:Type[_T]) -> _T:
  if to not in (str, Any, object):
    raise ConversionError(source, syntax, f'expected {to}; received str?')
  return syntax.value(source) # type: ignore[return-value]


_bools = [('false', False), ('no', False), ('true', True), ('yes', True)]

_bool_vals:Dict[str,bool] = { kx : v
  for k, v in _bools
    for kx in [k, k.capitalize(), k.upper(), k[0], k[0].upper()] }


@convert_eon.register
def convert_eon_empty(syntax:EonEmpty, source:Source, to:Type[_T]) -> _T:
  if to in (Any, object, None): return None # type: ignore[return-value]
  rtt = get_origin(to) or to
  try: return rtt()
  except Exception as e:
    raise ConversionError(source, syntax, f'expected {_fmt_type(to)}; received empty tree.\n{_fmt_exc(e)}') from e


@convert_eon.register
def convert_eon_list(syntax:EonList, source:Source, to:Type[_T]) -> _T:
  rtt, el_type, field_types, as_seq = _list_type_info(to)

  if field_types is None: # Use single element type.
    try:
      args = (convert_eon(el, source, el_type) for el in syntax.els)
      if as_seq: return rtt(args) # type: ignore[no-any-return]
      else: return rtt(*args) # type: ignore[no-any-return]
    except ConversionError as e:
      e.add_in_note(syntax, f'list -> {_fmt_type(to)}')
      raise
    except Exception as e:
      raise ConversionError(source, syntax,
        f'expected {_fmt_type(to)}; received list.\nElement type: {el_type}.\n{_fmt_exc(e)}') from e
  else:
    lft = len(field_types)
    if lft < len(syntax.els): # Do not tolerate excessive arguments.
      print(field_types)
      raise ConversionError(source, syntax.els[lft], f'expected {_fmt_type(to)}; received list. Argument #{lft} is excessive.')
    # If there are more fields than arguments, try it anyway; perhaps some of them have defaults. `zip` stops when els run out.
    try:
      args = (convert_eon(el, source, ft) for el, ft in zip(syntax.els, field_types))
      if as_seq: return rtt(args) # type: ignore[no-any-return]
      else: return rtt(*args) # type: ignore[no-any-return]
    except ConversionError as e:
      e.add_in_note(syntax, f'list -> {_fmt_type(to)}')
      raise
    except Exception as e:
      raise ConversionError(source, syntax, f'expected {_fmt_type(to)} structure; received list.\n{_fmt_exc(e)}') from e


@memoize
def _list_type_info(to:Type) -> tuple[type,Any,Optional[tuple[Any,...]],bool]:
  'Returns (rtt, el_type, field_types, as_seq).'
  if to in (Any, object): return (list, Any, None, True)
  rtt = get_origin(to) or to
  type_args = get_type_args(to)

  # Tuple types require special handling.
  if issubclass(rtt, tuple):
    lta = len(type_args)
    if lta == 2 and type_args[1] == Ellipsis: # Treat as sequence.
      el_type = type_args[0]
      return (rtt, el_type, None, True)
    elif rtt is tuple: # Treat plain tuple as struct.
      return (rtt, None, type_args, True)
    else: # Assume this is an annotated tuple subclass.
      type_hints = get_type_hints(to)
      return (rtt, None, tuple(type_hints.values()), True)

  el_type = type_args[0] if type_args else Any
  return (rtt, el_type, None, True)


@convert_eon.register
def convert_eon_dict(syntax:EonDict, source:Source, to:Type[_T]) -> _T:

  rtt:Type[_T]
  try: is_mapping, rtt, key_type, val_type, pars = _dict_type_info(to)
  except _SignatureError as e:
    msg = e.args[0]
    raise ConversionError(source, syntax, f'expected {_fmt_type(to)}; {msg}') from e

  if is_mapping:
    rtt_mapping:Callable[[Iterable],_T] = rtt
    try: return rtt_mapping((convert_eon(sk, source, key_type), convert_eon(sv, source, val_type)) for sk, sv in syntax.items)
    except ConversionError as e:
      e.add_in_note(syntax, f'dict -> {_fmt_type(to)}')
      raise
    except Exception as e:
      raise ConversionError(source, syntax, f'expected {_fmt_type(to)}; received dict.\n{_fmt_exc(e)}') from e
  else:
    args:Dict[str,Any] = {}
    try:
      for sk, sv in syntax.items:
        k:str = convert_eon(sk, source, str)
        try: v_type = pars[k]
        except KeyError as e:
          raise ConversionError(source, syntax, f'expected {_fmt_type(to)} ({pars}); invalid parameter: {k!r}') from e
        v = convert_eon(sv, source, v_type)
        args[k] = v
      return rtt(**args)
    except ConversionError as e:
      e.add_in_note(syntax, f'dict -> {_fmt_type(to)}')
      raise
    except Exception as e:
      raise ConversionError(source, syntax, f'expected {_fmt_type(to)} structure; received dict.\n{_fmt_exc(e)}') from e


@memoize
def _dict_type_info(to:Type) -> tuple[bool,type,Any,Any,Dict[str,Any]]:
  'Returns (is_mapping, rtt, key_type, val_type, parameters).'
  if to in (Any, object): return (True, dict, Any, Any, {})

  # Determine if `to` is a runtime type, and get the rtt regardless.
  rtt = get_origin(to) or to

  if issubclass(rtt, Mapping):
    type_args = get_type_args(to)
    lta = len(type_args)
    if lta == 0:
      kt, vt = (Any, Any)
    elif lta == 1:
      kt = type_args[0]
      vt = Any
    else:
      kt, vt = type_args[:2]
    return (True, rtt, kt, vt, {})

  # Assume struct-like type. Get parameter types from either __init__ or __new__.
  if rtt.__init__ != _object_init:
    constructor = rtt.__init__
  elif rtt.__new__ != _object_new:
    constructor = rtt.__new__
  else:
    raise _SignatureError(f'no typed constructor information available for {rtt}')
  sig = signature(constructor)
  pars = { p.name : _parameter_type(p) for p in list(sig.parameters.values())[1:] } # Skip the 'self' or 'cls' argument.
  return (False, rtt, None, None, pars)

_object_init = object.__init__
_object_new = object.__new__


class _SignatureError(Exception): pass


def _parameter_type(p:Parameter) -> Any:
  t = p.annotation
  if p.kind != Parameter.POSITIONAL_OR_KEYWORD:
    raise _SignatureError(f'parameter kind {t.kind} not supported: {p}')
  if t is Parameter.empty: return Any
  if isinstance(t, str): raise _SignatureError(f'string parameter types not supported: {p}')
  return t


def _fmt_exc(exc:Exception) -> str:
  msg = f'{type(exc).__name__}: {exc}'
  if not msg.endswith('.'): msg += '.'
  return msg


def _fmt_type(t:Any) -> str:
  try: return str(t.__name__)
  except AttributeError: pass
  n = str(t)
  n = _typing_re.sub('', n)
  return n

_typing_re = re.compile(r'\b\w+\.')


lexer = Lexer(flags='x',
  patterns=dict(
    newline = r'\n',
    spaces  = r'\ +',
    comment = r'//[^\n]*\n',

    # TODO: section labels.

    sym = r'[A-Za-z_][0-9A-Za-z_\-\./]*',
    flt = r'[0-9]+\.[0-9]+',
    int = r'[0-9]+',

    colon = r':',
    dash = r'-',
    tilde = r'~',
    brack_o = r'\[',
    brack_c = r'\]',
    paren_o = r'\(',
    paren_c = r'\)',
    dq = r'"',
    sq = r"'",

    esc_char=r'\\[n\\"\']',
    chars_dq=r'[^\n\\"]+',
    chars_sq=r"[^\n\\']+",
  ),
  modes=[
    LexMode('main',
      kinds=[
        'newline', 'spaces', 'comment', 'sym', 'flt', 'int', 'colon', 'dash', 'tilde',
        'brack_o', 'brack_c', 'paren_o', 'paren_c', 'dq', 'sq'],
      indents=True),
    LexMode('string_dq', kinds=['chars_sq', 'esc_char', 'dq']),
    LexMode('string_sq', kinds=['chars_sq', 'esc_char', 'sq']),
  ],
  transitions=[
    LexTrans('main', kind='dq', mode='string_dq', pop='dq', consume=True),
    LexTrans('main', kind='sq', mode='string_sq', pop='sq', consume=True),
  ],
)


def _build_eon_parser() -> Parser:
  return Parser(lexer,
    drop=('comment', 'spaces'),
    literals=('newline', 'indent', 'dedent', 'colon'),
    rules=dict(
      #sections=OneOrMore('section', drop='newline', transform=transform_sections),

      #section=Struct(Atom('section_label'), 'items'),

      key=Choice('flt', 'int', 'str_dq', 'str_sq', 'sym', transform=choice_val),

      leaf=Struct(
        Choice('flt', 'int', 'str_dq', 'str_sq', 'sym', transform=choice_val),
        'newline'),

      str_dq=Struct('dq', ZeroOrMore(Choice('esc_char', 'chars_dq', transform=choice_val)), 'dq',
        transform=lambda s, slc, fields: EonStr(slc, fields[1])),

      str_sq=Struct('sq', ZeroOrMore(Choice('esc_char', 'chars_sq', transform=choice_val)), 'sq',
        transform=lambda s, slc, fields: EonStr(slc, fields[1])),

      # Values always consume trailing newline.
      value=Choice('leaf', 'dash_list', 'tilde_dict', transform=choice_val),


      dash_list=Struct(
        'dash',
        Choice('newline', 'value', transform=lambda s, slc, label, val: None if label == 'newline' else val),
        Opt('list_body_multiline', dflt=()),
        transform=lambda s, slc, fields: EonList(slc=slc, els=[fields[1], *fields[2]] if fields[1] else fields[2])),

      list_body_multiline=Struct('indent', OneOrMore('value', drop='newline'), 'dedent'),


      tilde_dict=Struct(
        'tilde',
        Choice('newline', 'kv_pair', transform=lambda s, slc, label, pair: () if label == 'newline' else (pair,)),
        Opt('dict_body_multiline', dflt=()),
        transform=lambda s, slc, fields: EonDict(slc=slc, items=[*fields[1], *fields[2]])),

      dict_body_multiline=Struct('indent', OneOrMore('kv_pair', drop='newline'), 'dedent'),

      kv_pair=Struct('key', 'colon', 'value', transform=lambda s, slc, f: (f[0], f[2])),

      # Items are sequences of either all list items, or all dict key-value pairs.
      # The returned value is inferred to be either a list or dict.
      items=ZeroOrMore('item', drop='newline', transform=transform_items),

      item=Choice('keylike_item', 'dash_list', 'tilde_dict', transform=transform_item),

      keylike_item=Struct('key', 'newline_or_colon_body'),

      newline_or_colon_body=Choice('newline', 'colon_body',
        transform=lambda s, slc, label, val: None if label == 'newline' else val), # Newline implies that the just-parsed key is a list element.

      colon_body=Struct('colon', 'body'),

      body=Choice('value', 'body_multiline', transform=choice_val),

      body_multiline=Struct('newline', 'indent', 'items', 'dedent'),
    ),
  )


# Parser transformers.


def transform_items(source:Source, slc:slice, items:List[tuple[Any,Any]]) -> EonContainer:
  is_dict:bool
  vals:List[Any] = []
  for token, p in items:
    k, v = p
    is_pair = (v is not None) # None is never returned by value transformers, so it is a sufficient discriminator.
    if not vals:
      is_dict = is_pair
    elif is_dict != is_pair: # Inconsistent.
      if is_pair:
        msg = 'Expected list elements; received key-value pair.'
      else:
        msg = 'Expected key-value pair; received list element.'
      raise ParseError(source, token, 'inconsistent sequence. ' + msg, notes=[(slc, 'note: first element is here.')])
    vals.append(p if is_pair else k)
  if not vals:
    return EonEmpty(slc=slc)
  if is_dict:
    return EonDict(slc=slc, items=vals)
  else:
    return EonList(slc=slc, els=vals)


def transform_item(source:Source, slc:slice, label:str, item:Any) -> tuple[slice,Any]:
  if label == 'keylike_item':
    assert len(item) == 3
    return (slc, (item.key, item.newline_or_colon_body))
  else: return (slc, (item, None))


eon_parser = _build_eon_parser()


def main() -> None:
  '''
  Parse specified files (or stdin) as EON and print each result.'
  '''
  from sys import argv

  from .io import outD

  args = argv[1:] or ['/dev/stdin']
  for path in args:
    with open(path) as f:
      text = f.read()
    try: obj:Any = parse_eon(path, text, to=object)
    except ParseError as e: e.fail()
    outD(path, obj)


if __name__ == '__main__': main()
