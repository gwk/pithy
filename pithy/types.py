# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from abc import ABCMeta, abstractmethod
from collections import Counter as _Counter
from typing import Any, Callable, Dict, Optional, Protocol, Tuple, TypeVar, Union


_T = TypeVar('_T')

NoneType = type(None)
Opt = Optional


class Comparable(Protocol):
  # taken from https://www.python.org/dev/peps/pep-0484/.
  @abstractmethod
  def __lt__(self, other:Any) -> bool: ...

  @abstractmethod
  def __eq__(self, other:Any) -> bool: ...


def is_a(val:Any, T:Union[type, Tuple[type, ...]]) -> bool:
  '''
  Test if `val` is of `T`. Unlike `isinstance`,
  this function works with generic static types.
  '''
  try: return isinstance(val, T)
  except TypeError as e:
    if e.args[0] != 'Subscripted generics cannot be used with class and instance checks': raise
  RTT = T.__origin__ # type: ignore # The runtime type for the static type.
  args = T.__args__  # type: ignore
  try:
    predicate = _generic_type_predicates[RTT]
  except KeyError: # Not specialized.
    if issubclass(RTT, dict): # Two parameters.
      if issubclass(RTT, _Counter): # Counter only has one type parameter.
        K = args[0]
        V = int # Note that Counters can have non-int values inserted.
      else:
        K, V = args
      return isinstance(val, RTT) and all(is_a(k, K) and is_a(v, V) for (k, v) in val.items())
    elif len(args) == 1: # Assume `T` is a single-parameter generic container.
      E = args[0]
      return isinstance(val, RTT) and all(is_a(el, E) for el in val)
    else:
      raise TypeError(f'{T} is not a single-parameter generic type; origin type: {RTT}')
  else: # Specialized.
    # Union is an extra strange case, because the origin type is not a runtime type either.
    return (RTT is Union or isinstance(val, RTT)) and predicate(val, args)


_Args = Tuple[Any, ...]

def _is_a_Tuple(v:Any, args:_Args) -> bool:
  if len(args) == 2 and args[1] is Ellipsis:
    E = args[0]
    return all(is_a(el, E) for el in v)
  else:
    return len(v) == len(args) and all(is_a(el, E) for (el, E) in zip(v, args))

_generic_type_predicates: Dict[Any, Callable[[Any, _Args], bool]] = {
  tuple: _is_a_Tuple,
  Union: lambda v, args: any(is_a(v, Member) for Member in args),
}


# Convenience type predicates.

def is_bool(val: Any) -> bool: return isinstance(val, bool)

def is_float(val: Any) -> bool: return isinstance(val, float)

def is_int(val: Any) -> bool: return isinstance(val, int)

def is_str(val: Any) -> bool: return isinstance(val, str)

def is_list(val: Any, of:Optional[type]=None) -> bool:
  return isinstance(val, list) and (of is None or all(isinstance(el, of) for el in val))

def is_set(val: Any, of:Optional[type]=None) -> bool:
  return isinstance(val, set) and (of is None or all(isinstance(el, of) for el in val))

def is_dict(val: Any, of:Optional[type]=None) -> bool:
  return isinstance(val, dict) and (of is None or all(isinstance(el, of) for el in val))

def is_tuple(val: Any, of:Optional[type]=None, length:Optional[int]=None) -> bool:
  return isinstance(val, tuple) and (length is None or length == len(val)) and (of is None or all(isinstance(el, of) for el in val))

def is_int_or_bool(val: Any) -> bool: return isinstance(val, (int, bool))

def is_list_of_str(val: Any) -> bool: return isinstance(val, list) and all(isinstance(el, str) for el in val)

def is_set_of_str(val: Any) -> bool: return isinstance(val, set) and all(isinstance(el, str) for el in val)

def is_tuple_of_str(val: Any, length:Optional[int]=None) -> bool:
  return is_tuple(val, of=str, length=length)

def is_dict_of_str(val: Any) -> bool:
  return isinstance(val, dict) and all(isinstance(k, str) and isinstance(v, str) for (k, v) in val.items())

def is_pair_of_str(val: Any) -> bool: return is_tuple(val, of=str, length=2)

def is_pair_of_int(val: Any) -> bool: return is_tuple(val, of=int, length=2)

def is_str_or_list(val: Any) -> bool: return is_str(val) or is_list_of_str(val)

def is_str_or_pair(val: Any) -> bool: return is_str(val) or is_pair_of_str(val)

def is_pos_int(val: Any) -> bool: return is_int(val) and bool(val > 0)


def req_type(obj: _T, expected: Union[type, Tuple[type, ...]]) -> _T:
  'Return `obj` if it is of `expected` type, or else raise a descriptive TypeError.'
  if not is_a(obj, expected):
    raise TypeError(f'expected type: {expected}; actual type: {type(obj)};\n  object: {obj!r}')
  return obj
