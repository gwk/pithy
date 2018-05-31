# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from abc import ABCMeta, abstractmethod
from typing import *


T = TypeVar('T')

class Comparable(metaclass=ABCMeta):
  # taken from https://www.python.org/dev/peps/pep-0484/.
  @abstractmethod
  def __lt__(self, other: Any) -> bool: ...


# type predicates.

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


def is_a(obj: Any, expected: Union[type, Tuple[type, ...]]) -> bool:
  '''
  Python's typing objects are explicitly disallowed from being used in isinstance.
  We work around this as best we can, relying on the descriptions of generic types.
  '''
  desc = str(expected)
  generic = desc.partition('[')[0]
  if generic == 'typing.Union':
    for member_type in expected.__args__: # type: ignore
      if is_a(obj, member_type): return True
    return False
  try: rtt = runtime_generic_type_prefixes[generic]
  except KeyError: pass
  else: return isinstance(obj, rtt) # approximate; best effort.
  return isinstance(obj, expected)

runtime_generic_type_prefixes: Dict[str, type] = {
  'typing.List' : list,
  'typing.Set' : set,
  'typing.Dict' : dict,
  # TODO: complete.
}


def req_type(obj: T, expected: Union[type, Tuple[type, ...]]) -> T:
  if not is_a(obj, expected):
    raise TypeError(f'expected type: {expected}; actual type: {type(obj)};\n  object: {obj!r}')
  return obj
