# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from abc import abstractmethod
from dataclasses import is_dataclass
from typing import Any, Callable, Counter, Dict, get_args, get_origin, Optional, Protocol, Tuple, TypeVar, Union


_T = TypeVar('_T')

NoneType = type(None)
Opt = Optional


class Comparable(Protocol):
  # taken from https://www.python.org/dev/peps/pep-0484/.
  @abstractmethod
  def __lt__(self, other:Any) -> bool: ...

  @abstractmethod
  def __eq__(self, other:Any) -> bool: ...


def is_a(val:Any, T:Union[type,tuple[type,...]]) -> bool:
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

  raise TypeError(f'{T} is not a single-parameter generic type; origin type: {RTT}')


_Args = Tuple[type, ...]


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


_generic_type_predicates: Dict[Any, Callable[[Any, _Args], bool]] = {
  tuple: _is_a_Tuple,
  Union: _is_a_Union,
}


def is_type_namedtuple(t:type) -> bool:
  '''
  Return `True` if `t` appears to be a `namedtuple` type.
  This is a guess based on the attributes of `t`.
  '''
  return issubclass(t, tuple) and namedtuple_type_expected_attrs.intersection(t.__dict__) == namedtuple_type_expected_attrs

namedtuple_type_expected_attrs = frozenset({'_asdict', '_field_defaults', '_fields', '_make', '_replace'})


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

def is_int_or_bool(val: Any) -> bool: return isinstance(val, (int, bool))

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


def req_type(obj: _T, expected:Union[type,Tuple[type,...]]) -> _T:
  'Return `obj` if it is of `expected` type, or else raise a descriptive TypeError.'
  if not is_a(obj, expected):
    raise TypeError(f'expected type: {expected}; actual type: {type(obj)};\n  object: {obj!r}')
  return obj
