# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from functools import singledispatch
from inspect import Parameter, signature
from typing import Any, Callable, get_args as get_type_args, get_origin, get_type_hints, Mapping, TypeVar

from tolkien import Source, Token

from ..util import memoize
from .parse import ConversionError
from .syntax import EonList, EonStr, EonSyntax


_T = TypeVar('_T')


@singledispatch
def convert_eon(syntax:EonSyntax, source:Source, to:type[_T]) -> _T:
  'Convert eon AST to a generic data value.'
  raise NotImplementedError(f'unimplemented syntax type: {syntax}')


@convert_eon.register
def convert_eon_token(syntax:Token, source:Source, to:type[_T]) -> _T:
  text = source[syntax]
  if to is str: return text
  if to is bool: return _bool_vals[text]
  if to in (Any, object):
    if syntax.kind == 'sym': return text
    if syntax.kind == 'int': return int(text)
    if syntax.kind == 'flt': return float(text)
    raise NotImplementedError(syntax)
  rtt = get_origin(to) or to
  try: return rtt(text)
  except Exception as e:
    raise ConversionError(source, syntax, f'expected {_fmt_type(to)}; received {syntax.kind}.\n{_fmt_exc(e)}') from e


@convert_eon.register
def convert_eon_str(syntax:EonStr, source:Source, to:type[_T]) -> _T:
  if to not in (str, Any, object):
    raise ConversionError(source, syntax, f'expected {to}; received {syntax.token.kind}.')
  return syntax.value(source) # type: ignore


_bools = [('false', False), ('no', False), ('true', True), ('yes', True)]

_bool_vals:dict[str,bool] = { kx : v
  for k, v in _bools
    for kx in [k, k.capitalize(), k.upper(), k[0], k[0].upper()] }


@convert_eon.register
def convert_eon_list(syntax:EonList, source:Source, to:type[_T]) -> _T:
  converter_fn = _list_converter_fn(to)
  return converter_fn(syntax, source)




@memoize
def _list_converter_fn(to:type) -> Callable[[EonList,Source],Any]:
  'Returns the memoized converter function for the argument type.'

  if to in (Any, object, list): return convert_eon_to_plain_list

  runtime_type = get_origin(to) or to
  type_args = get_type_args(to)

  # Tuple types require special handling because they can be sequence-like or struct-like.
  if issubclass(runtime_type, tuple):
    if len(type_args) == 2 and type_args[1] == Ellipsis: # Treat tuple type as sequence.
      return _list_to_seq_converter_fn(runtime_type=runtime_type, el_type=type_args[0])
    elif runtime_type is tuple: # Untyped tuple;
      return _list_to_struct_converter_fn(runtime_type=runtime_type, field_types=type_args, as_seq=True)
    else: # Assume this is an annotated tuple subclass.
      type_hints = get_type_hints(to)
      field_types = type_hints.values()
      return _list_to_struct_converter_fn(runtime_type=runtime_type, field_types=field_types, as_seq=True)

  el_type = type_args[0] if type_args else Any
  return (rtt, el_type, None, True)

def _list_to_seq_converter_fn(runtime_type:type, el_type:type) -> Callable[[EonList,Source],Any]:
  def convert_eon_to_seq(syntax:EonList, source:Source) -> Any:
    return runtime_type(convert_eon(el, source, el_type) for el in syntax.els)
  return convert_eon_to_seq

def _list_to_struct_converter_fn(to:type, rtt:type) -> Callable[[EonList,Source],Any]:
  ''

def convert_eon_to_plain_list(syntax:EonList, source:Source) -> list:
  return [convert_eon(el, source, Any) for el in syntax.els]

def thing():
  rtt, el_type, field_types, as_seq = _list_type_info(to)

  if field_types is None: # Use single element type.
    try:
      args = (convert_eon(el, source, el_type) for el in syntax.els)
      if as_seq: return rtt(args) # type: ignore
      else: return rtt(*args) # type: ignore
    except ConversionError as e:
      e.add_in_note(syntax.token, f'list -> {_fmt_type(to)}')
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
      if as_seq: return rtt(args) # type: ignore
      else: return rtt(*args) # type: ignore
    except ConversionError as e:
      e.add_in_note(syntax.token, f'list -> {_fmt_type(to)}')
      raise
    except Exception as e:
      raise ConversionError(source, syntax, f'expected {_fmt_type(to)} structure; received list.\n{_fmt_exc(e)}') from e


'''
@convert_eon.register
def convert_eon_dict(syntax:EonDict, source:Source, to:type[_T]) -> _T:

  rtt:type[_T]
  try: is_mapping, rtt, key_type, val_type, pars = _dict_type_info(to)
  except _SignatureError as e:
    msg = e.args[0]
    raise ConversionError(source, syntax, f'expected {_fmt_type(to)}; {msg}') from e

  if is_mapping:
    rtt_mapping:Callable[[Iterable],_T] = rtt
    try: return rtt_mapping((convert_eon(sk, source, key_type), convert_eon(sv, source, val_type)) for sk, sv in syntax.items)
    except ConversionError as e:
      e.add_in_note(syntax.token, f'dict -> {_fmt_type(to)}')
      raise
    except Exception as e:
      raise ConversionError(source, syntax, f'expected {_fmt_type(to)}; received dict.\n{_fmt_exc(e)}') from e
  else:
    args:dict[str,Any] = {}
    try:
      for sk, sv in syntax.items:
        k:str = convert_eon(sk, source, str)
        try: v_type = pars[k]
        except KeyError as e:
          raise ConversionError(source, syntax, f'expected {_fmt_type(to)} ({pars}); invalid parameter: {k!r}') from e
        v = convert_eon(sv, source, v_type)
        args[k] = v
      return rtt(**args) # type: ignore
    except ConversionError as e:
      e.add_in_note(syntax.token, f'dict -> {_fmt_type(to)}')
      raise
    except Exception as e:
      raise ConversionError(source, syntax, f'expected {_fmt_type(to)} structure; received dict.\n{_fmt_exc(e)}') from e
'''

@memoize
def _dict_type_info(to:type) -> tuple[bool,type,Any,Any,dict[str,Any]]:
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
