# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Callable, FrozenSet, Iterable, Set, Type, cast


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
