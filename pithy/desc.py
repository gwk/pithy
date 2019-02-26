# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from sys import stderr
from typing import Any, Iterable, Iterator, List, Mapping, TextIO, Tuple

from .tree import known_leaf_types


def writeD(file:TextIO, obj:Any, depth:int=0) -> None:
  for line in gen_desc(obj, depth=depth):
    print(line, file=file)


def errD(obj:Any, depth:int=0) -> None:
  for line in gen_desc(obj, depth=depth):
    print(line, file=stderr)


def outD(obj:Any, depth:int=0) -> None:
  for line in gen_desc(obj, depth=depth):
    print(line)


def gen_desc(obj:Any, depth:int=0) -> Iterator[str]:
  width = 128
  buffer:List[str] = []
  buffer_depth = depth

  def needs_multiline() -> bool:
    return False

  def flush(multiline:bool=False) -> Iterator[str]:
    ind = '  ' * buffer_depth
    if multiline or needs_multiline():
      last = len(buffer) - 1
      for i, el in enumerate(buffer):
        comma = ', ' if i < last else ''
        yield f'{ind}{el}{comma}'
    else:
      yield ind + ', '.join(buffer)
    buffer.clear()

  for d, s in gen_obj_desc(obj, depth=depth):
    if d < 0: # Closer.
      assert buffer
      buffer[-1] += s if (buffer[-1][-1] in ']})') else ' '+s
    elif d < buffer_depth:
      yield from flush()
      buffer_depth = d
      buffer.append(s)
    elif d > buffer_depth: # Entered deeper.
      yield from flush(multiline=True)
      buffer_depth = d
      buffer.append(s)
    else: # Same depth.
      buffer.append(s)

  yield from flush()


def gen_obj_desc(obj:Any, depth:int) -> Iterator[Tuple[int,str]]:
  if isinstance(obj, known_leaf_types):
    yield (depth, repr(obj))
    return

  if hasattr(obj, 'items'): # Treat as a mapping.
    yield from gen_dict_desc(obj, depth=depth)
    return

  try: it = iter(obj)
  except TypeError: pass
  else:
    yield from gen_iter_desc(obj, it, depth=depth)
    return

  yield (depth, repr(obj))


def gen_dict_desc(obj:Mapping, depth:int) -> Iterator[Tuple[int,str]]:
  is_dict = isinstance(obj, dict)
  head = '{' if is_dict else (type(obj).__qualname__ + '({')
  yield (depth, head)
  for k, v in obj.items():
    vg = gen_obj_desc(v, depth+1)
    v1d, v1s = next(vg)
    ks = f'{k!r}: {v1s}'
    yield (depth+1, ks)
    yield from vg
  yield (-1, '}' if is_dict else '})')


def gen_iter_desc(obj:Any, it:Iterator, depth:int) ->  Iterator[Tuple[int,str]]:
  is_list = isinstance(obj, list)
  head = '[' if  is_list else (type(obj).__qualname__ + '([')
  yield (depth, head)
  for el in it: yield from gen_obj_desc(el, depth+1)
  yield (-1, ']' if is_list else '])')
