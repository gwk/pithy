# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import asdict as dc_asdict
from functools import singledispatch
from types import GetSetDescriptorType, MemberDescriptorType
from typing import Any, Callable, Type

from .date import Date, DateTime, Time
from .type_utils import is_dataclass_instance
from .util import memoize


EncodeObj = Callable[[Any],Any]

@singledispatch
def encode_obj(obj:Any) -> Any:
  '''
  Encode an object for serialization, e.g. to json or msgpack.
  This function is used for the default `default` converter by `render_json`, `write_json`, `write_msgpack`.

  Note: it is not possible to encode namedtuple as a JSON dict using a `default` function such as this,
  because the namedtuple gets converted to a list without ever calling `default`.
  '''

  try: # Try to convert to a sequence first.
    _ = len(obj) # Check that length is implemented first; we do not want to encode infinite iterators.
    it = iter(obj)
  except TypeError: pass
  else: return list(it)

  if is_dataclass_instance(obj): return dc_asdict(obj)

  # Attempt to determine generic data attributes.
  d = {}
  for name in get_data_attr_names(type(obj)):
    try: d[name] = getattr(obj, name)
    except AttributeError: pass

  if instance_dict := getattr(obj, '__dict__', None):
    for k, v in instance_dict.items():
      d[k] = v

  if d: return d

  raise TypeError(f'cannot encode object of type {type(obj).__qualname__}')


@encode_obj.register
def _(obj:None) -> Any: return obj

@encode_obj.register
def _(obj:bool) -> Any: return obj

@encode_obj.register
def _(obj:int) -> Any: return obj

@encode_obj.register
def _(obj:str) -> Any: return obj

@encode_obj.register
def _(obj:type) -> Any: return obj.__name__


@encode_obj.register
def _(obj:Date) -> Any: return obj.isoformat()

@encode_obj.register
def _(obj:DateTime) -> Any: return obj.isoformat(sep=' ')

@encode_obj.register
def _(obj:Time) -> Any: return obj.isoformat()


@memoize
def get_data_attr_names(cls:Type) -> tuple[str,...]:
  '''
  Attempt to get the names of apparent data attributes of a class.
  '''
  names = []
  for name in dir(cls):
    if name.startswith('_'): continue
    try: type_attr = getattr(cls, name)
    except AttributeError: continue
    if isinstance(type_attr, (MemberDescriptorType, GetSetDescriptorType)):
      names.append(name)
  return tuple(names)
