# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import asdict, is_dataclass
from functools import singledispatch
from typing import Any, Callable, FrozenSet, Set, Type

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

  try: it = iter(obj) # Try to convert to a sequence first.
  except TypeError: pass
  else: return list(it)

  if is_dataclass(obj): return asdict(obj)

  if hasattr(obj, '__slots__'):
    slots = all_slots(type(obj))
    slots = slots.union(getattr(obj, '__dict__', ())) # Slots classes may also have backing dicts.
    return {a: getattr(obj, a) for a in slots}

  try: d = obj.__dict__ # Treat other classes as dicts by default.
  except AttributeError: pass
  else:
    if any(k.startswith('_') for k in d): # Only create a new dictionary if necessary.
      return {k:v for k,v in d.items() if not k.startswith('_')}
    else:
      return d

  return str(obj) # convert to string as last resort.


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


@memoize()
def all_slots(type: Type) -> FrozenSet[str]:
  '''
  Subclasses of slots classes may define their own slots,
  which hold just the additions to the parent class.
  Therefore we need to iterate over the inheritance chain to get all slot names.
  We use __mro__ here, and hope for the best regarding multiple inheritance.
  '''
  slots: Set[str] = set()
  for t in type.__mro__:
    try: s = t.__slots__ # type: ignore[attr-defined]
    except AttributeError: break
    else:
      if isinstance(s, str): slots.add(s) # single slot.
      else:
        slots.update(s)
  return frozenset(slots)
