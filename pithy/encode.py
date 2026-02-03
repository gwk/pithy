# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import asdict as dc_asdict
from functools import singledispatch
from typing import Any, Callable

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

  if hasattr(obj, '__slots__'):
    slots = all_slots(type(obj))
    if d := getattr(obj, '__dict__', None):
      slots += tuple(k for k in d.keys() if k not in slots)

    return {a: getattr(obj, a) for a in slots if not a.startswith('_')}

  try: d = obj.__dict__ # Treat other classes as dicts by default.
  except AttributeError: pass
  else:
    if any(k.startswith('_') for k in d): # Only create a new dictionary if necessary.
      return {k:v for k,v in d.items() if not k.startswith('_')}
    else:
      return d

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


@memoize()
def all_slots(type:type) -> tuple[str,...]:
  '''
  Subclasses of slots classes may define their own slots, which hold just the additions to the parent class.
  Therefore we need to iterate over the inheritance chain to get all slot names.
  See: https://docs.python.org/3/reference/datamodel.html#slots.
  Note: a slot in a child class masks a slot of the same name in a parent class.
  The slots are returned in the order they are defined, from parent to child.
  '''
  slots_set: set[str] = set()
  slots_seq = []
  for t in type.__mro__: # Iterate from child to parent.
    try: raw_slots = t.__slots__ # type: ignore[attr-defined]
    except AttributeError: break # A subclass that does not define its own slots will have that of its parent; ok to stop.
    else:
      slots = (raw_slots.split() if isinstance(raw_slots, str) else raw_slots)
      for s in reversed(slots):
        if s not in slots_set: # Child slots mask parents.
          # Note: this assumes that the slot is not repeated within the class. If it is, the order will be last-wins.
          slots_set.add(s)
          slots_seq.append(s)

  return tuple(reversed(slots_seq))
