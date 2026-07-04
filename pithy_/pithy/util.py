# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import importlib
from typing import Any, Callable, Iterable, NamedTuple, TypeVar


_T = TypeVar('_T')


def load_and_execute(module_name:str, function_name:str, /, *args:Any, **kwargs:Any) -> Any:
  'Load a module and execute the specified function.'
  module = importlib.import_module(module_name)
  func = getattr(module, function_name)
  return func(*args, **kwargs)


def resolve_module_spec(spec:str, *, default_attr:str='') -> Any:
  '''
  Resolve a `module[:attr]` spec string to an object.
  The module is imported by its full dotted path, so its containing package initializes normally.
  `attr` may itself be dotted; if it is omitted, `default_attr` is used when provided, otherwise the module is returned.
  '''
  module_name, _, attr = spec.partition(':')
  module = importlib.import_module(module_name)
  if not attr: attr = default_attr
  obj:Any = module
  if attr:
    for part in attr.split('.'):
      obj = getattr(obj, part)
  return obj


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


def once(fn:Callable[[],_T]) -> _T:
  'Call the decorated function and return its result.'
  return fn()
