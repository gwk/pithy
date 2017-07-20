# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from abc import ABCMeta, abstractmethod
from typing import *


class Comparable(metaclass=ABCMeta):
  # taken from https://www.python.org/dev/peps/pep-0484/.
  @abstractmethod
  def __lt__(self, other: Any) -> bool: ...


# type predicates.

def is_bool(val: Any) -> bool: return isinstance(val, bool)

def is_int(val: Any) -> bool: return isinstance(val, int)

def is_str(val: Any) -> bool: return isinstance(val, str)

def is_list(val: Any) -> bool: return isinstance(val, list)

def is_set(val: Any) -> bool: return isinstance(val, set)

def is_dict(val: Any) -> bool: return isinstance(val, dict)

def is_tuple(val: Any) -> bool: return isinstance(val, tuple)

def is_pair(val: Any) -> bool: return isinstance(val, tuple) and len(val) == 2

def is_int_or_bool(val: Any) -> bool: return is_int(val) or is_bool(val)

def is_list_of_str(val: Any) -> bool: return is_list(val) and all(is_str(el) for el in val)

def is_set_of_str(val: Any) -> bool: return is_set(val) and all(is_str(el) for el in val)

def is_dict_of_str(val: Any) -> bool:
  return is_dict(val) and all(is_str(k) and is_str(v) for (k, v) in val.items())

def is_pair_of_str(val: Any) -> bool:
  return is_pair(val) and is_str(val[0]) and is_str(val[1])

def is_pair_of_int(val: Any) -> bool:
  return is_pair(val) and is_int(val[0]) and is_int(val[1])

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


def req_type(obj: Any, expected: Union[type, Tuple[type, ...]]) -> None:
  if not is_a(obj, expected):
    raise TypeError(f'expected type: {expected}; actual type: {type(obj)};\n  object: {obj!r}')
