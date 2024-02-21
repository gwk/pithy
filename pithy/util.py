# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Callable, Iterable, NamedTuple, TypeVar


_T = TypeVar('_T')


class lazy_property(object):
  '''
  Lazy property decorator. This is similar to functools.cached_property, but more simplistic.
  This is not thread safe. As of Python 3.12, neither is cached_property.
  Thus we could conceivably retire lazy_property entirely.
  '''

  def __init__(self, acc_fn:Callable):
    self.acc_fn = acc_fn

  def __get__(self, obj:Any, cls:type) -> Any:
    val = self.acc_fn(obj)
    setattr(obj, self.acc_fn.__name__, val)
    return val


def memoize(_fn:Callable|None=None, sentinel:Any=Ellipsis) -> Callable:
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


def nt_items(nt:NamedTuple) -> Iterable[tuple[str,Any]]:
  'Return an iterable that returns the (name, value) pairs of a NamedTuple.'
  return zip(nt._fields, nt)


def nonopt(optional:_T|None) -> _T:
  'Return the value of an optional, raising an exception if it is None.'
  if optional is None: raise ValueError
  return optional


def once(fn:Callable[[],_T]) -> _T: return fn()
