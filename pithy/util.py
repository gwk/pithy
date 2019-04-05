# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from functools import singledispatch
from typing import Any, Callable, Dict, FrozenSet, Iterable, NamedTuple, Set, Tuple, Type, cast

from dataclasses import asdict, is_dataclass


def memoize(_fn:Callable=None, sentinel:Any=Ellipsis) -> Callable:
  '''
  recursive function memoization decorator.
  results will be memoized by a key that is the tuple of all arguments.
  the sentinel is inserted into the dictionary before the call.
  thus, if the function recurses with identical arguments the sentinel will be returned to the inner calls.
  '''

  def _memoize(fn:Callable) -> Callable:

    class MemoDict(dict):
      def __repr__(self) -> str: return f'@memoize({sentinel}){fn}'
      def __call__(self, *args:Any) -> Any: return self[args]
      def __missing__(self, args:Any) -> Any:
        self[args] = sentinel
        res = fn(*args)
        self[args] = res
        return res

    return MemoDict()

  if _fn is None: # called parens.
    return _memoize
  else: # called without parens.
    return _memoize(_fn)


class lazy_property(object):
  'Lazy property decorator.'

  def __init__(self, acc_fn:Callable) -> None:
    self.acc_fn = acc_fn

  def __get__(self, obj:Any, cls:Type) -> Any:
    val = self.acc_fn(obj)
    setattr(obj, self.acc_fn.__name__, val)
    return val


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
    try: s = t.__slots__
    except AttributeError: break
    else:
      if isinstance(s, str): slots.add(s) # single slot.
      else:
        slots.update(s)
  return frozenset(slots)


def nt_items(nt:NamedTuple) -> Iterable[Tuple[str,Any]]:
  'Return an iterable that returns the (name, value) pairs of a NamedTuple.'
  return zip(nt._fields, nt)


EncodeObj = Callable[[Any],Any]

@singledispatch
def encode_obj(obj:Any) -> Any:
  '''
  Encode an object for serialization, e.g. to json or msgpack.
  This function is used for the default `default` converter by `render_json`, `write_json`, `write_msgpack`.

  Note: it is not possible to encode namedtuple as a JSON dict using a `default` function such as this,
  because the namedtuple gets converted to a list without ever calling `default`.
  For that reason, we do not even try.
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

@encode_obj.register # type: ignore
def _(obj:bool) -> Any: return obj

@encode_obj.register # type: ignore
def _(obj:int) -> Any: return obj

@encode_obj.register # type: ignore
def _(obj:str) -> Any: return obj

@encode_obj.register # type: ignore
def _(obj:type) -> Any: return repr(obj)
