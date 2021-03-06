# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Callable, Iterable, NamedTuple, Tuple, Type, TypeVar


class lazy_property(object):
  'Lazy property decorator.'

  def __init__(self, acc_fn:Callable) -> None:
    self.acc_fn = acc_fn

  def __get__(self, obj:Any, cls:Type) -> Any:
    val = self.acc_fn(obj)
    setattr(obj, self.acc_fn.__name__, val)
    return val


_T = TypeVar('_T')

def once(fn:Callable[[],_T]) -> _T: return fn()


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


def nt_items(nt:NamedTuple) -> Iterable[Tuple[str,Any]]:
  'Return an iterable that returns the (name, value) pairs of a NamedTuple.'
  return zip(nt._fields, nt)
