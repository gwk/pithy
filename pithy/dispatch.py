# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import inspect
from functools import wraps
from typing import Any, Callable, DefaultDict, Dict, Optional, Tuple

from .default import Default


class DispatchKeyError(KeyError): pass


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
      raise TypeError(f'argument to @key_dispatched() must be key function; received {key_fn!r}')
    if key is not Default._:
      raise ValueError(f'@key_dispatched() requires either positional `key_fn` (decorating default method) or keyword `key`')
    if key_fn.__closure__ is not None: # type: ignore # Key function cannot be a closure.
      raise ValueError(f'@key_dispatched() `key_fn` cannot be a closure; recieved {key_fn!r}')

    def dflt_decorator(dflt_method:Callable)->Callable:
      _check_key_dispatched_method(dflt_method)
      # Check for collision.
      name = dflt_method.__name__
      module_registry = _keyed_dispatch_registries[dflt_method.__module__]
      if name in module_registry:
        raise DispatchKeyError(f'`@key_dispatched()` collision on method name: {name}')
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
      raise ValueError(f'@key_dispatched() takes either positional `key_fn` (decorating default method) or keyword `key`')

    def decorator(method:Callable) -> Callable:
      _check_key_dispatched_method(method)
      # Check for collision.
      name = method.__name__
      module_registry = _keyed_dispatch_registries[method.__module__]
      try: dispatch, method_registry = module_registry[name]
      except KeyError as e:
        raise DispatchKeyError(f'@key_dispatched() method name was not previously registered: {name}') from e
      if key in method_registry:
        raise DispatchKeyError(f'@key_dispatched() collision on key: {key}') # TODO: show previous implementation.
      method_registry[key] = method
      return dispatch
    return decorator


def _check_key_dispatched_method(method:Callable) -> None:
  if method.__closure__ is not None: # type: ignore # Method cannot be a closure because it is registered globally.
    raise ValueError(f'@key_dispatched() decorated method cannot be a closure; recieved {method!r}')
  sig = inspect.signature(method)
  pars = list(sig.parameters.values())
  if len(pars) < 2 or pars[0].name not in ('self', 'cls'):
    raise TypeError(f'@key_dispatched() decorated method requires at least `self` and one additional parameter; received {method!r}')
