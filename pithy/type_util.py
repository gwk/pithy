# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any


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

def is_pos_int(val: Any) -> bool: return is_int(val) and val > 0


def req_type(object: Any, class_info):
  if not isinstance(object, class_info):
    raise TypeError('expected type: {}; actual type: {};\n  object: {}'.format(
      class_info, type(object), repr(object)))
