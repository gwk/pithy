# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import inspect
from functools import _find_impl, wraps # type: ignore
from typing import Any, Callable, DefaultDict, Dict, Optional, Tuple, TypeVar, cast

from .default import Default


class DispatchKeyError(KeyError): pass
class DispatchTypeError(TypeError): pass


# module_name -> method_name -> arg_type.
_dispatched_registries = DefaultDict[str, DefaultDict[str, Dict[type, Callable]]](lambda: DefaultDict(dict))

_Method = TypeVar('_Method', bound=Callable)

def dispatched(method:_Method) -> _Method:
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

  return cast(_Method, dispatch)


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
_keyed_dispatch_registries = DefaultDict[str, Dict[str, Tuple[Callable, Dict[Any, Callable]]]](dict)

def key_dispatched(key_fn:Optional[Callable[[Any], Any]]=None, *, key:Any=Default._) -> Callable[[Callable], Callable]:
  '''
  Decorator to register a method as the dispatched method for the specified key.
  Usage:
    @key_dispatched
  '''

  if key_fn is not None: # register new dispatcher name with default implementation.
    if not callable(key_fn):
      raise TypeError(f'argument to key_dispatched() must be key function; received {key_fn!r}')
    if key is not Default._:
      raise ValueError(f'@key_dispatch() takes either positional `key_fn` (decorating default method) or keyword `key`')
    if key_fn.__closure__ is not None: # type: ignore # Key function cannot be a closure.
      raise ValueError(f'@key_dispatch() `key_fn` cannot be a closure; recieved {key_fn!r}')

    def dflt_decorator(dflt_method:Callable)->Callable:
      _check_key_dispatched_method(dflt_method)
      # Check for collision.
      name = dflt_method.__name__
      module_registry = _keyed_dispatch_registries[dflt_method.__module__]
      if name in module_registry:
        raise DispatchKeyError(f'`keyed_dispatch` collision on method name: {name}')
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

  else: # key_fn is None; register implementation for key.
    if key is Default._:
      raise ValueError(f'@key_dispatch() takes either positional `key_fn` (decorating default method) or keyword `key`')

    def decorator(method:Callable) -> Callable:
      _check_key_dispatched_method(method)
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


def _check_key_dispatched_method(method:Callable) -> None:
  if method.__closure__ is not None: # type: ignore # Method cannot be a closure because it is registered globally.
    raise ValueError(f'@key_dispatch() decorated method cannot be a closure; recieved {method!r}')
  sig = inspect.signature(method)
  pars = list(sig.parameters.values())
  if len(pars) < 2 or pars[0].name != 'self':
    raise TypeError(f'`keyed_dispatch` decorated method requires at least `self` and one additional parameter; received {method!r}')
