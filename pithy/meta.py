# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import inspect
from importlib.machinery import ModuleSpec
from inspect import FrameInfo
from types import FrameType
from typing import Any, Callable, cast, Iterable, Mapping, TypeVar


class MetaprogrammingError(Exception): pass


def bindings_matching(*, prefix:str|None=None, val_type:type|None=None, strip_prefix=True, frame='<module>') -> list[tuple[str, Any]]:
  '''
  Return (name, value) pairs of bindings from the specified frame,
  that match the specified prefix and val_type filters.
  Frame must be either an int (depth; immediate caller is 1),
  or a string (the name of the target frame's function, or '<module>', the default).
  '''
  stack = inspect.stack()
  info: FrameInfo|None
  if isinstance(frame, int):
    info = stack[frame]
  elif isinstance(frame, str):
    info = None
    for info in stack:
      if info.function == frame:
        break
    if info is None:
      raise ValueError('call stack does not contain a matching frame: {}'.format(frame))
  else:
    raise TypeError("frame parameter must be either an int (depth; immediate caller is 1), "
      "or a string (the name of the target frame's function, or '<module>', the default).")
  bindings = info.frame.f_locals
  pairs = []
  for name, value in bindings.items():
    if all((
      prefix is None or name.startswith(prefix),
      val_type is None or isinstance(value, val_type),
    )):
      if prefix and strip_prefix:
        name = name[len(prefix):]
      pairs.append((name, value))
  return pairs


def dispatcher_for_defs(*, prefix:str, default: Callable|None=None, base:Mapping[str,Callable]={}, exclude:Iterable[str]=()) -> Callable:
  '''
  Creates a dispatcher function from callable definitions in the caller's module.
  Only callables whose name starts with `prefix` are included.
  `default` is another callable; it will receive all of the arguments to the dispatcher (including the first string argument)
  when no particular dispatch function matches.
  '''

  _exclude = {exclude} if isinstance(exclude, str) else set(exclude)

  bindings:dict[str,Callable] = dict(base)
  for name, fn in bindings_matching(prefix=prefix, frame='<module>', strip_prefix=True):
    if (name in bindings) or (name in _exclude) or (not callable(fn)): continue
    bindings[name] = fn

  if default is None:
    def dispatch_fn(name, *args, **kwargs):
      fn = bindings[name]
      try: return fn(*args, **kwargs)
      except TypeError as exc: raise DispatchException(fn) from exc
  else:
    def dispatch_fn(name, *args, **kwargs):
      try: fn = bindings[name]
      except KeyError: pass # Handled below.
      else:
        try: return fn(*args, **kwargs)
        except TypeError as exc: raise DispatchException(fn) from exc
      return default(name, *args,  **kwargs)

  setattr(dispatch_fn, 'bindings', bindings)
  setattr(dispatch_fn, 'default', default)
  return dispatch_fn


class DispatchException(Exception): pass


_A = TypeVar('_A', bound=Any)

def rename(obj:_A, name:str|None=None, module:str|None=None) -> _A:
  'Returns `obj`, after renaming name and/or module.'
  if name is not None:
    obj.__name__ = name
    obj.__qualname__ = name
  if module is not None:
    obj.__module__ = module
  return obj


def caller_frame(steps:int) -> FrameType:
  '''
  Returns the call frame `steps` above the immediate caller.
  steps=0 is useful when calling this function from the module scope.
  steps=1 is useful when calling this function from a function that wants to know about its own caller.
  '''
  f = inspect.currentframe() # This frame.
  if f is None: raise MetaprogrammingError('no current frame')
  f = f.f_back # Immediate caller's frame.
  if f is None: raise MetaprogrammingError('no caller frame')
  for i in range(steps):
    p = f
    f = f.f_back
    if f is None: raise MetaprogrammingError(f'no caller frame (step {i+1}); previous: {p!r}')
  return f


def caller_module_spec(steps:int) -> ModuleSpec:
  '''
  Returns the ModuleSpec of the parent module `steps` number of frames from the immediate caller.
  steps=0 is useful when this function is called from the module scope.
  steps=1 is useful when this function is called from a function that wants to know about its own caller.
  '''
  f = caller_frame(steps)
  spec = f.f_globals['__spec__']
  if spec is None:
    desc = f'{f.f_code.co_filename}:{f.f_lineno}:{f.f_code.co_name}'
    raise MetaprogrammingError(f'no module spec for caller frame: {desc!r}')
  if not isinstance(spec, ModuleSpec):
    raise MetaprogrammingError(f'caller frame has invalid module spec: {spec!r}')
  return spec


def caller_module_name(steps:int) -> str|None:
  '''
  Get the module name of the caller name, `steps` number of frames from the immediate caller.
  steps=0 is useful when called from the module scope.
  steps=1 is useful when called from a function that wants to know the name of the caller's module.
  '''
  try: f = caller_frame(steps)
  except MetaprogrammingError: return None
  spec = f.f_globals['__spec__']
  if spec: return cast(str, spec.name)
  else: return cast(str, f.f_globals['__name__'])


def caller_pkg_path(steps:int) -> str:
  '''
  Returns the path of the package containing the caller, `steps` number of frames from the immediate caller.
  steps=0 is useful when called from the module scope.
  steps=1 is useful when called from a function that wants to know the path of the caller's package.
  '''
  f = caller_frame(steps)
  spec = f.f_globals['__spec__']
  if spec is None: raise MetaprogrammingError(f'no module spec for caller frame: {f!r}')
  locations = spec.submodule_search_locations
  if locations is None:
    desc = f'{f.f_code.co_filename}:{f.f_lineno}:{f.f_code.co_name}()'
    raise MetaprogrammingError(f'no submodule search locations for frame: {desc}')
  return cast(str, spec.submodule_search_locations[0])


def main_file_path() -> str:
  'Returns the main file path.'
  import __main__
  path: str = __main__.__file__
  return path
