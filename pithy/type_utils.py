# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from abc import abstractmethod
from collections import Counter
from dataclasses import Field, is_dataclass
from types import UnionType
from typing import (Any, Callable, cast, ClassVar, get_args, get_origin, Literal, overload, Protocol, runtime_checkable, TypeIs,
  TypeVar, Union)


_T = TypeVar('_T')

NoneType = type(None)


@runtime_checkable
class Comparable(Protocol):
  # taken from https://www.python.org/dev/peps/pep-0484/.
  @abstractmethod
  def __lt__(self, other:Any) -> bool: ...

  @abstractmethod
  def __eq__(self, other:Any) -> bool: ...


def is_a(val:Any, T:type|tuple[type,...]) -> bool:
  '''
  Test if `val` is of `T`.
  Unlike `isinstance`, this function works with basic generic types.
  '''
  if isinstance(T, tuple): return any(is_a(val, t) for t in T)

  args = get_args(T)
  if not args: return isinstance(val, T)
  RTT = get_origin(T)

  if RTT is None: raise TypeError(f'{T} has no origin type')

  try: predicate = _generic_type_predicates[RTT]
  except KeyError: pass
  else: return predicate(val, args)

  if issubclass(RTT, dict): # Two parameters.
    if issubclass(RTT, Counter): # Counter only has one type parameter.
      K = args[0]
      V = int # Note that Counters can have non-int values inserted.
    else:
      K, V = args
    return isinstance(val, RTT) and all(is_a(k, K) and is_a(v, V) for (k, v) in val.items())

  if len(args) == 1: # Assume `T` is a single-parameter generic container.
    E = args[0]
    return isinstance(val, RTT) and all(is_a(el, E) for el in val)

  raise TypeError(f'{T} is not a single-parameter generic type; origin type: {RTT}; args: {args}')


_Args = tuple[type, ...]


def _is_a_Tuple(v:Any, args:_Args) -> bool:
  if not isinstance(v, tuple): return False
  if len(args) == 2 and args[1] is Ellipsis:
    E = args[0] # type: ignore[unreachable]
    return all(is_a(el, E) for el in v)
  else:
    return len(v) == len(args) and all(is_a(el, E) for (el, E) in zip(v, args))


def _is_a_Union(v:Any, args:_Args) -> bool:
  # Union is an extra strange case, because the origin type is not a runtime type either.
  return any(is_a(v, Member) for Member in args)


_generic_type_predicates: dict[Any, Callable[[Any, _Args], bool]] = {
  tuple: _is_a_Tuple,
  Union: _is_a_Union,
  UnionType: _is_a_Union,
}


def is_type_namedtuple(t:type) -> bool:
  '''
  Return `True` if `t` appears to be a `namedtuple` type.
  This is a guess based on the attributes of `t`.
  '''
  return issubclass(t, tuple) and namedtuple_type_expected_attrs.intersection(t.__dict__) == namedtuple_type_expected_attrs

namedtuple_type_expected_attrs = frozenset({'_asdict', '_field_defaults', '_fields', '_make', '_replace'})


def is_type_dataclass(t:type) -> bool:
  return issubclass(t, tuple) and is_dataclass(t)


class DataclassInstance(Protocol):
  'Copied from typeshed/stdlib/_typeshed/__init__.py.'
  __dataclass_fields__: ClassVar[dict[str, Field[Any]]]


def is_dataclass_instance(obj:Any) -> TypeIs[DataclassInstance]:
  '''
  Returns `True` if `obj` is a dataclass instance. Returns `False` for all type objects.
  It is often more correct to use this function rather than `is_dataclass`
  it is easy to forget that `is_dataclass` returns `True` for types
  and many use cases do not intend to let type objects through.
  This function is annotated as returning `TypeIs[DataclassInstance]`
  to aid the type checker in narrowing the type of `obj`.
  '''
  return not isinstance(obj, type) and is_dataclass(obj)


def is_namedtuple(obj:Any) -> bool:
  '''
  Return `True` if `obj` appears to be a `namedtuple` instance or type.
  Like is_dataclass, this accepts both instances and types.
  '''
  return is_type_namedtuple(obj if isinstance(obj, type) else type(obj))


def is_dataclass_or_namedtuple(obj:Any) -> bool:
  '''
  is_dataclass works for both instances and types.
  This function offers a similarly flexible check for both dataclass and namedtuple instances/types.
  '''
  return is_dataclass(obj) or is_namedtuple(obj)


# Convenience type predicates.

def is_bool(val: Any) -> bool: return isinstance(val, bool)

def is_float(val: Any) -> bool: return isinstance(val, float)

def is_int(val: Any) -> bool: return isinstance(val, int)

def is_str(val: Any) -> bool: return isinstance(val, str)

def is_list(val: Any, of:type|None=None) -> bool:
  return isinstance(val, list) and (of is None or all(isinstance(el, of) for el in val))

def is_set(val: Any, of:type|None=None) -> bool:
  return isinstance(val, set) and (of is None or all(isinstance(el, of) for el in val))

def is_dict(val: Any, of:type|None=None) -> bool:
  return isinstance(val, dict) and (of is None or all(isinstance(el, of) for el in val))

def is_tuple(val:Any, of:type|None=None, length:int|None=None) -> bool:
  return isinstance(val, tuple) and (length is None or length == len(val)) and (of is None or all(isinstance(el, of) for el in val))

def is_list_of_str(val: Any) -> bool: return isinstance(val, list) and all(isinstance(el, str) for el in val)

def is_set_of_str(val: Any) -> bool: return isinstance(val, set) and all(isinstance(el, str) for el in val)

def is_tuple_of_str(val: Any, length:int|None=None) -> bool:
  return is_tuple(val, of=str, length=length)

def is_dict_of_str(val: Any) -> bool:
  return isinstance(val, dict) and all(isinstance(k, str) and isinstance(v, str) for (k, v) in val.items())

def is_pair_of_str(val: Any) -> bool: return is_tuple(val, of=str, length=2)

def is_pair_of_int(val: Any) -> bool: return is_tuple(val, of=int, length=2)

def is_str_or_list(val: Any) -> bool: return is_str(val) or is_list_of_str(val)

def is_str_or_pair(val: Any) -> bool: return is_str(val) or is_pair_of_str(val)

def is_pos_int(val: Any) -> bool: return is_int(val) and bool(val > 0)


def is_literal(val:Any, of_type:Any) -> bool:
  '''
  Return `True` if `val` is a member of the `of_type` literal type.
  Unfortunately mypy treats `literal['x']` as a <typing special form>  and not a type,
  so `of_type` cannot be declared as `type` or `type[Literal]`.
  Furthermore it appears impossible to implement a generic `req_literal` function as of mypy 1.11.
  '''
  if get_origin(of_type) != Literal: raise TypeError(f'expected Literal type; received: {of_type!r}')
  return val in get_args(of_type)


def req_type(obj:Any, expected:type[_T]) -> _T:
  'Return `obj` if it is of `expected` type, or else raise a descriptive TypeError.'
  if not is_a(obj, expected):
    raise TypeError(f'expected type: {expected}; actual type: {type(obj)};\n  object: {obj!r}')
  return cast(_T, obj)


def req_bool(obj:Any) -> bool:
  if not isinstance(obj, bool): raise TypeError(f'expected type: bool; actual type: {type(obj)}; value: {obj!r}')
  return obj

def req_int(obj:Any) -> int:
  if not isinstance(obj, int): raise TypeError(f'expected type: int; actual type: {type(obj)}; value: {obj!r}')
  return obj

def req_float(obj:Any) -> float:
  if not isinstance(obj, float): raise TypeError(f'expected type: float; actual type: {type(obj)}; value: {obj!r}')
  return obj

def req_str(obj:Any) -> str:
  if not isinstance(obj, str): raise TypeError(f'expected type: str; actual type: {type(obj)}; value: {obj!r}')
  return obj


def req_opt_bool(obj:Any) -> bool|None:
  if not (obj is None or isinstance(obj, bool)):
    raise TypeError(f'expected type: bool; actual type: {type(obj)}; value: {obj!r}')
  return obj

def req_opt_int(obj:Any) -> int|None:
  if not (obj is None or isinstance(obj, int)):
    raise TypeError(f'expected type: int; actual type: {type(obj)}; value: {obj!r}')
  return obj

def req_opt_float(obj:Any) -> float|None:
  if not (obj is None or isinstance(obj, float)):
    raise TypeError(f'expected type: float; actual type: {type(obj)}; value: {obj!r}')
  return obj

def req_opt_str(obj:Any) -> str|None:
  if not (obj is None or isinstance(obj, str)):
    raise TypeError(f'expected type: str; actual type: {type(obj)}; value: {obj!r}')
  return obj


_El = TypeVar('_El')


@overload
def req_list(obj:Any) -> list: ...

@overload
def req_list(obj:Any, of:type[_El]) -> list[_El]: ...

def req_list(obj:Any, of:type[_El]|None=None) -> list[_El]:
  if not isinstance(obj, list): raise TypeError(f'expected type: list; actual type: {type(obj)}; value: {obj!r}')
  if of is not None:
    for el in obj:
      if not isinstance(el, of):
        raise TypeError(f'expected type: {of}; actual type: {type(el)}; value: {el!r}')
  return obj


@overload
def req_opt_list(obj:Any) -> list: ...

@overload
def req_opt_list(obj:Any, of:type[_El]) -> list[_El]: ...

def req_opt_list(obj:Any, of:type[_El]|None=None) -> list|None:
  if obj is None: return None
  if not isinstance(obj, list):
    raise TypeError(f'expected type: list|None; actual type: {type(obj)}; value: {obj!r}')
  if of is not None:
    for el in obj:
      if not isinstance(el, of):
        raise TypeError(f'expected type: {of}; actual type: {type(el)}; value: {el!r}')
  return obj


_K = TypeVar('_K')
_V = TypeVar('_V')

@overload
def req_dict(obj:Any) -> dict: ...

@overload
def req_dict(obj:Any, K:type[_K], V:type[_V]) -> dict[_K,_V]: ...

def req_dict(obj:Any, K:type=object, V:type=object) -> dict:
  if not isinstance(obj, dict): raise TypeError(f'expected type: dict; actual type: {type(obj)}; value: {obj!r}')
  if K is not object or V is not object:
    for k, v in obj.items():
      if not isinstance(k, K):
        raise TypeError(f'expected key type: {K}; actual type: {type(k)}; value: {k!r}')
      if not isinstance(v, V):
        raise TypeError(f'expected value type: {V}; actual type: {type(v)}; value: {v!r}')
  return obj


@overload
def req_opt_dict(obj:Any) -> dict|None: ...

@overload
def req_opt_dict(obj:Any, K:type[_K], V:type[_V]) -> dict[_K,_V]|None: ...

def req_opt_dict(obj:Any, K:type=object, V:type=object) -> dict|None:
  if obj is None: return None
  if not isinstance(obj, dict):
    raise TypeError(f'expected type: dict|None; actual type: {type(obj)}; value: {obj!r}')
  if K is not object or V is not object:
    for k, v in obj.items():
      if not isinstance(k, K):
        raise TypeError(f'expected key type: {K}; actual type: {type(k)}; value: {k!r}')
      if not isinstance(v, V):
        raise TypeError(f'expected value type: {V}; actual type: {type(v)}; value: {v!r}')
  return obj
