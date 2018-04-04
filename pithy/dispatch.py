# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import inspect
from collections import defaultdict
from functools import wraps, _find_impl # type: ignore
from weakref import WeakKeyDictionary
from typing import Any, Callable, DefaultDict, Dict


class DispatchTypeError(TypeError): pass


# module_name -> method_name -> arg_type.
_registries: DefaultDict[str, DefaultDict[str, Dict[type, Callable]]] = defaultdict(lambda: defaultdict(dict))

def dispatched(method: Callable) -> Callable:
  '''
  Decorator for instance methods to dispatch on first arg (after self).
  Uses the same MRO resolution algorithm as functools.singledispatch.

  Usage:
  | class C():
  |
  |  @dispatched
  |  def describe(self, item:int) -> None: print(f'int: {item}')
  |
  |  @dispatched
  |  def describe(self, item:str) -> None: print(f'str: {item}')

  TODO: poison registration mechanism after first call to prevent subtle MRO/caching errors.
  '''
  assert method.__closure__ is None # type: ignore # Method cannot be a closure.
  registry = _registries[method.__module__][method.__name__]
  sig = inspect.signature(method)
  pars = list(sig.parameters.values())
  par_self = pars[0]
  par_arg = pars[1]
  assert par_self.name == 'self'
  t = par_arg.annotation
  assert isinstance(t, type)
  if t in registry:
    a = _source_loc(registry[t])
    b = _source_loc(method)
    raise DispatchTypeError(f'`dispatched` methods collide on argument type:\n{a}\n{b}')
  registry[t] = method

  dispatch_cache: Dict[type, Callable] = {}
  @wraps(method)
  def dispatch(self, arg, *args, **kwargs):
    method = _dispatch(type(arg), registry, dispatch_cache)
    return method(self, arg, *args, **kwargs)
  return dispatch


def _source_loc(function: Callable) -> str:
  code = function.__code__
  return f'{code.co_filename}:{code.co_firstlineno}'


def _dispatch(cls: type, registry: Dict[type, Callable], dispatch_cache: Dict[type, Callable]) -> Callable:
  try: return dispatch_cache[cls]
  except KeyError: pass
  try:
    m = dispatch_cache[cls] = registry[cls]
    return m
  except KeyError: pass
  try: m = _find_impl(cls, registry)
  except RuntimeError as e: raise DispatchTypeError(cls) from e
  if m is None: raise DispatchTypeError(cls)
  dispatch_cache[cls] = m
  return m
