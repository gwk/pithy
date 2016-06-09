import inspect

from types import FunctionType


def bindings_matching(prefix=None, type=None, strip_prefix=True, frame='<module>'):
  '''
  return (name, value) pairs of bindings from the specified frame, 
  that match the specified prefix and type filters.
  frame must be either an int (depth; immediate caller is 1),
  or a string (the name of the target frame's function, or '<module>', the default).
  '''
  stack = inspect.stack()
  if isinstance(frame, int):
    bindings = stack[depth].frame.f_globals
  elif isinstance(frame, str):
    bindings = None
    for frame_info in stack:
      if frame_info.function == frame:
        bindings = frame_info.frame.f_globals
        break
    if bindings is None:
      raise ValueError('call stack does not contain a matching frame: {}'.format(frame))
  else:
    raise TypeError("frame parameter must be either an int (depth; immediate caller is 1), "
      "or a string (the name of the target frame's function, or '<module>', the default).")
  pairs = []
  for name, value in bindings.items():
    if all((
      prefix is None or name.startswith(prefix),
      type is None or isinstance(value, type),
    )):
      if prefix and strip_prefix:
        name = name[len(prefix):]
      pairs.append((name, value))
  return pairs


def dispatcher_for_names(prefix=None, default_name=None, default_fn=None):
  assert prefix
  bindings = dict(bindings_matching(prefix=prefix, type=FunctionType, frame='<module>'))
  if default_name is not None:
    if default_fn is not None:
      raise ValueError('default_name and default_fn cannot both be specified.')
    default_fn = bindings[default]
  
  def dispatch_fn(name, *args, **kwargs):
    try:
      fn = bindings[name]
    except KeyError:
      if default_fn is None: raise
      fn = default_fn
    return fn(*args, **kwargs)

  return dispatch_fn


def rename(obj, name):
  obj.__name__ = name
  obj.__qualname__ = name
  return obj


def main_file_path():
  import __main__
  return __main__.__file__
