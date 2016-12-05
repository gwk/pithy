# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import inspect
from inspect import FrameInfo
from types import FunctionType
from typing import Any, Callable, List, Optional, Tuple, TypeVar


def bindings_matching(prefix: str=None, val_type: type=None, strip_prefix=True, frame='<module>') -> List[Tuple[str, Any]]:
  '''
  Return (name, value) pairs of bindings from the specified frame,
  that match the specified prefix and type filters.
  Frame must be either an int (depth; immediate caller is 1),
  or a string (the name of the target frame's function, or '<module>', the default).
  '''
  stack = inspect.stack()
  info: Optional[FrameInfo]
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


def dispatcher_for_names(prefix: str=None, default_name: str=None, default_fn: Callable=None, **renames) -> Callable:
  'Creates a dispatcher function for functions starting with prefix.'
  assert prefix
  bindings = { renames.get(name, name) : fn
    for name, fn in bindings_matching(prefix=prefix, val_type=FunctionType, frame='<module>') }

  if default_name is not None:
    if default_fn is not None:
      raise ValueError('default_name and default_fn cannot both be specified.')
    default_fn = bindings[default_name]

  def dispatch_fn(name, *args, **kwargs):
    try:
      fn = bindings[name]
    except KeyError:
      if default_fn is None: raise
      fn = default_fn
    return fn(*args, **kwargs)

  return dispatch_fn


A = TypeVar('A', bound=Any)

def rename(obj: A, name: str) -> A:
  'Returns a renamed object.'
  obj.__name__ = name
  obj.__qualname__ = name
  return obj


def main_file_path() -> str:
  'Returns the main file path.'
  import __main__ # type: ignore
  return __main__.__file__
