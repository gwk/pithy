# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import inspect
from functools import update_wrapper
from types import MappingProxyType
from typing import Any, Callable, cast, Concatenate, Generic, ParamSpec, TypeAlias, TypeVar


class DispatchKeyError(KeyError):
    pass


_O = TypeVar('_O') # Object type (the class defining the method).
_A = TypeVar('_A') # The type of the first argument to the method (not including `self` or `cls`).
_K = TypeVar('_K') # The key type derived from the first argument.
type _KF[_A,_K] = Callable[[_A], _K] # Key function.
_P = ParamSpec('_P') # The type of the additional parameters to the method.
_R = TypeVar('_R') # The return type of the method.
_BM:TypeAlias = Callable[Concatenate[_A, _P], _R] # Bound method.
_UM:TypeAlias = Callable[Concatenate[_O, _A, _P], _R] # Unbound method (first argument is `self` or `cls`).


class KeyDispatchMethod(Generic[_O, _A, _K, _P, _R]):

  def __init__(self, key_fn:_KF, default_method:_UM) -> None:

    if key_fn.__closure__ is not None:
        raise ValueError(f'`key_fn` cannot be a closure; received {callable!r}')

    _check_key_dispatched_method(default_method)

    self.key_fn = key_fn
    self.default_method = default_method
    self._method_registry:dict[_K,_UM] = {}
    self.method_registry = MappingProxyType[_K,_UM](self._method_registry)


  def __get__(self, obj:_O, cls:type|None=None) -> _BM:

    def key_dispatch_closure(arg:_A, *args:_P.args, **kwargs:_P.kwargs) -> _R:
      key = self.key_fn(arg)
      method:_UM = self.method_registry.get(key, self.default_method)
      bound_method:_BM = method.__get__(obj, cls)
      return cast(_R, bound_method(arg, *args, **kwargs))

    update_wrapper(key_dispatch_closure, self.default_method)

    return key_dispatch_closure


  def register(self, key:_K) -> Callable[[_UM], _UM]:

    def decorator(method:_UM) -> _UM:
      'The decorator that registers a method for a specific key.'
      _check_key_dispatched_method(method)
      if key in self._method_registry:
          raise DispatchKeyError(f'Collision on key: {key}') # TODO: show previously registered implementation?
      self._method_registry[key] = method
      if getattr(method, '__name__', '_') == '_':
        # Update the nameless registered method with the name of the default method.
        update_wrapper(method, self.default_method, assigned=('__name__', '__qualname__'), updated=())
      return method

    return decorator


def key_dispatched_method(key_fn:_KF) -> Callable[[_UM], KeyDispatchMethod]:
  '''
  Decorator to create a method that dispatches over table of keys.

  # Usage
  ```
  class C:

    @key_dispatched(key_fn) # `key_fn` takes the first argument and returns a key.
    def method(self, key:KeyType, *args, **kwargs): ... # The default implementation.

    @fn.register("k0")
    def impl(arg:KeyType, *args, **kwargs): ... # An implementation for a specific key "k0".
  ```
  '''

  def _decorator(default_method: Callable) -> KeyDispatchMethod:
    'The returned decorator for `key_dispatched_method`. This is used to decorate the default method.'
    return KeyDispatchMethod(key_fn, default_method)

  return _decorator


def _check_key_dispatched_method(method:Any) -> None:
  #^ Note: `method` is untyped because this is a runtime check and it may be a descriptor.
  if not callable(method) and not hasattr(method, "__get__"):
    raise TypeError(f'decorated method is not callable or a descriptor: {method!r}')
  if getattr(method, '__closure__', None) is not None:
      raise ValueError(f'decorated method cannot be a closure: {method!r}')
  sig = inspect.signature(method)
  pars = list(sig.parameters.values())
  if len(pars) < 2 or pars[0].name not in ('self', 'cls'):
    raise TypeError(
      f'@key_dispatched_method() decorated method requires `self` | `cls` and at least one additional parameter; received {method!r}')
