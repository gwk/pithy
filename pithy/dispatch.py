# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import inspect
from collections import defaultdict
from functools import wraps, _find_impl # type: ignore
from weakref import WeakKeyDictionary
from typing import Any, Callable, DefaultDict, Dict, Optional, Tuple
from .default import Raise


class DispatchKeyError(KeyError): pass
class DispatchTypeError(TypeError): pass


# module_name -> method_name -> arg_type.
_dispatched_registries: DefaultDict[str, DefaultDict[str, Dict[type, Callable]]] = defaultdict(lambda: defaultdict(dict))

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
  TODO: detect method vs plain function?
  '''
  assert method.__closure__ is None # type: ignore # Method cannot be a closure.
  registry = _dispatched_registries[method.__module__][method.__name__]
  sig = inspect.signature(method)
  pars = list(sig.parameters.values())
  par_self = pars[0]
  par_arg = pars[1]
  assert par_self.name == 'self'
  t = par_arg.annotation
  if not isinstance(t, type):
    raise TypeError(f'`dispatched` requires type annotation to be a runtime type: {t}') # TODO: allow generics by using __origin__.
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
  '''
  Dispatch using functools.singledispatch algorithm.
  '''
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


# module_name -> method_name -> (dispatcher_method, key).
_keyed_dispatch_registries: DefaultDict[str, Dict[str, Tuple[Callable, Dict[Any, Callable]]]] = defaultdict(dict)

def key_dispatched(key_fn:Optional[Callable[[Any], Any]]=None, *, key:Any=Raise._) -> Callable[[Callable], Callable]:
  'Decorator to register a method as the dispatched method for the specified key.'

  if key_fn is not None: # register new dispatcher name with default implementation.
    assert key is Raise._
    assert key_fn.__closure__ is None # type: ignore
    def dflt_decorator(dflt_method:Callable)->Callable:
      assert dflt_method.__closure__ is None # type: ignore # Method cannot be a closure.
      # Check that the method looks appropriate.
      sig = inspect.signature(dflt_method)
      pars = list(sig.parameters.values())
      assert len(pars) >= 2, f'`keyed_dispatch dflt_method requires at least `self` and one additional parameter.'
      par_self = pars[0]
      assert par_self.name == 'self'
      # Check for collision.
      module_registry = _keyed_dispatch_registries[dflt_method.__module__]
      name = dflt_method.__name__
      if name in module_registry:
        suffix = '' if callable(key_fn) else '; did you mean `@keyed_dispatch(key=...)`?'
        raise DispatchKeyError(f'`keyed_dispatch` collision on method name: {name}{suffix}')
      # Register.
      method_registry: Dict[Any, Callable] = {}
      # Create and return dispatcher method.
      @wraps(dflt_method)
      def dispatch(self, arg, *args, **kwargs):
        f = method_registry.get(key_fn(arg), dflt_method) # type: ignore
        return f(self, arg, *args, **kwargs)
      module_registry[name] = (dispatch, method_registry)
      return dispatch
    return dflt_decorator

  else: # register implementation for key.
    assert key is not Raise._
    def decorator(method:Callable) -> Callable:
      assert method.__closure__ is None # type: ignore # Method cannot be a closure.
      # Check that the method looks appropriate.
      sig = inspect.signature(method)
      pars = list(sig.parameters.values())
      assert len(pars) >= 2, f'`keyed_dispatch method requires at least `self` and one additional parameter.'
      par_self = pars[0]
      assert par_self.name == 'self'
      # Check for collision.
      name = method.__name__
      module_registry = _keyed_dispatch_registries[method.__module__]
      try: dispatch, method_registry = module_registry[name]
      except KeyError as e:
        raise DispatchKeyError(f'`keyed_dispatch` method name was not previously registered: {name}') from e
      if key in method_registry:
        raise DispatchKeyError(f'`keyed_dispatch` collision on key: {key}') # TODO: show previous implementation.
      method_registry[key] = method
      return dispatch
    return decorator
