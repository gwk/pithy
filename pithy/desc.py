# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from sys import stderr, stdout
from typing import Any, Iterable, Iterator, List, Mapping, Optional, Set, TextIO, Tuple

from .tree import known_leaf_types


def writeD(file:TextIO, *labels_and_obj:Any, depth:int=0) -> None:
  obj = labels_and_obj[-1]
  labels = labels_and_obj[:-1]
  if labels: print(*labels, end=': ', file=file)
  for line in gen_desc(obj, depth=depth):
    print(line, file=file)


def errD(*labels_and_obj:Any, depth:int=0) -> None:
  writeD(stderr, *labels_and_obj, depth=depth)


def outD(*labels_and_obj:Any, depth:int=0) -> None:
  writeD(stdout, *labels_and_obj, depth=depth)


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
        comma = ',' if i < last else ''
        yield f'{ind}{el}{comma}'
    else: # Inline.
      yield ind + ', '.join(buffer)
    buffer.clear()

  for d, s in gen_obj_desc(obj, depth=depth, visited_ids=[]):
    if d < 0: # Closer.
      assert buffer
      buffer[-1] += s if (buffer[-1][-1] in '[]{}()') else ' '+s
    elif d < buffer_depth: # Pop level out.
      yield from flush()
      buffer_depth = d
      buffer.append(s)
    elif d > buffer_depth: # Push level in.
      yield from flush(multiline=True)
      buffer_depth = d
      buffer.append(s)
    else: # Same depth.
      buffer.append(s)

  yield from flush()


def gen_obj_desc(obj:Any, depth:int, visited_ids:List[int]) -> Iterator[Tuple[int,str]]:
  if isinstance(obj, known_leaf_types):
    yield (depth, repr(obj))
    return

  i = id(obj)
  if i in visited_ids:
    yield (depth, f'^0x{i:x}:{type(obj).__name__}')
    return

  # Most objects in a tree are leaves; we minimize tests for the leaf case by nesting the mapping test inside the iter test.
  # This has the side effect of ignoring non-iterable classes that have an irrelevant items() function.

  # Explicit test because iter() will return for objects without __iter__ but with __getitem__;
  # this includes typing._SpecialForm, which fails when we attempt to iterate.
  if hasattr(obj, '__iter__'):
    try: it = iter(obj)
    except TypeError: pass
    else:
      visited_ids.append(i)
      # Attempt to distinguish between mapping and sequence types.
      try: items = iter(obj.items()) # Wrapping `iter` guards against badly formed items() functions.
      except (AttributeError, TypeError): # Treat as iterable.
        yield from gen_iter_desc(obj, iter(obj), depth, visited_ids)
      else: # Treat as a mapping.
        yield from gen_mapping_desc(obj, items, depth, visited_ids)
      visited_ids.pop()
      return

  yield (depth, repr(obj))


def gen_mapping_desc(obj:Mapping, items:Iterator[Tuple[Any,Any]], depth:int, visited_ids:List[int]) -> Iterator[Tuple[int,str]]:
  is_dict = isinstance(obj, dict)
  head = '{' if is_dict else (type(obj).__qualname__ + '({')
  yield (depth, head)
  for pair in items:
    try: k, v = pair
    except (TypeError, ValueError):
      yield (depth+1, f'! {pair!r}')
      continue
    vg = gen_obj_desc(v, depth+1, visited_ids)
    v1d, v1s = next(vg)
    ks = f'{k!r}: {v1s}'
    yield (depth+1, ks)
    yield from vg
  yield (-1, '}' if is_dict else '})')


def gen_iter_desc(obj:Any, it:Iterator, depth:int, visited_ids:List[int]) ->  Iterator[Tuple[int,str]]:
  if isinstance(obj, list):
    head = '['
    close = ']'
  elif isinstance(obj, tuple):
    head = '('
    close = ',)' if len(obj) == 1 else ')'
  else:
    head = type(obj).__qualname__ + '(['
    close = '])'
  yield (depth, head)
  for el in it: yield from gen_obj_desc(el, depth+1, visited_ids)
  yield (-1, close)


def repr_clean(obj:Any) -> str:
  '''
  Attempt to ensure that an object gets printed with a decent repr.
  Some third-party libraries print unconventional reprs that are confusing inside of collection descriptions.
  '''
  r = repr(obj)
  if type(obj) in _literal_repr_types or _decent_repr_re.fullmatch(r): return r
  return f'{type(obj).__name__}({r})'

_literal_repr_types = { bytes,str,list,dict,set,tuple }
_decent_repr_re = re.compile(r'[a-zA-Z][.\w]*\(.*\)')


def repr_lim(obj:Any, limit=64) -> str:
  r = repr(obj)
  if len(r) <= limit: return r
  return r[:limit-1] + '…'
