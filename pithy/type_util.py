# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


# type predicates.

def is_bool(val): return isinstance(val, bool)

def is_int(val): return isinstance(val, int)

def is_str(val): return isinstance(val, str)

def is_list(val): return isinstance(val, list)

def is_set(val): return isinstance(val, set)

def is_dict(val): return isinstance(val, dict)

def is_tuple(val): return isinstance(val, tuple)

def is_int_or_bool(val): return is_int(val) or is_bol(val)

def is_list_of_str(val): return is_list(val) and all(is_str(el) for el in val)

def is_set_of_str(val): return is_set(val) and all(is_str(el) for el in val)

def is_dict_of_str(val):
  return is_dict(val) and all(is_str(k) and is_str(v) for (k, v) in val.items())

def is_pair_of_str(val):
  return is_tuple(val) and len(val) == 2 and is_str(val[0]) and is_str(val[1])

def is_str_or_list(val): return is_str(val) or is_list_of_str(val)

def is_str_or_pair(val): return is_str(val) or is_pair_of_str(val)

def is_pos_int(val): return is_int(val) and val > 0


def req_type(object, class_info):
  if not isinstance(object, class_info):
    raise TypeError('expected type: {}; actual type: {};\n  object: {}'.format(
      class_info, type(object), repr(object)))
