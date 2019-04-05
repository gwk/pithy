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


class _VisitedIds(Set[int]):

  def __init__(self, parent:Optional['_VisitedIds']) -> None:
    self.parent = parent

  def child(self) -> '_VisitedIds':
    return _VisitedIds(parent=self)

  def __contains__(self, key:int) -> bool: # type: ignore
    return super().__contains__(key) or (self.parent is not None and (key in self.parent))



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

  for d, s in gen_obj_desc(obj, depth=depth, visited_ids=_VisitedIds(parent=None)):
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


def gen_obj_desc(obj:Any, depth:int, visited_ids:_VisitedIds) -> Iterator[Tuple[int,str]]:
  if isinstance(obj, known_leaf_types):
    yield (depth, repr(obj))
    return

  try: items = obj.items()
  except (AttributeError, TypeError): pass
  else: # Treat as a mapping.
    i = id(obj)
    if i in visited_ids:
      yield (depth, '^')
    else:
      visited_ids.add(i)
      yield from gen_dict_desc(obj, items, depth, visited_ids)
    return

  # Explicit test because iter() will return an iterator for objects without __iter__ but with __getitem__;
  # this includes typing._SpecialForm, which then fails when you try to iterate.
  if hasattr(obj, '__iter__'):
    try: it = iter(obj)
    except TypeError: pass
    else:
      i = id(obj)
      if i in visited_ids:
        yield (depth, '^')
      else:
        yield from gen_iter_desc(obj, iter(obj), depth, visited_ids)
        return

  yield (depth, repr(obj))


def gen_dict_desc(obj:Mapping, items:Iterable[Tuple[Any,Any]], depth:int, visited_ids:_VisitedIds) -> Iterator[Tuple[int,str]]:
  is_dict = isinstance(obj, dict)
  head = '{' if is_dict else (type(obj).__qualname__ + '({')
  yield (depth, head)
  for k, v in items:
    vg = gen_obj_desc(v, depth+1, visited_ids.child())
    v1d, v1s = next(vg)
    ks = f'{k!r}: {v1s}'
    yield (depth+1, ks)
    yield from vg
  yield (-1, '}' if is_dict else '})')


def gen_iter_desc(obj:Any, it:Iterator, depth:int, visited_ids:_VisitedIds) ->  Iterator[Tuple[int,str]]:
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
  for el in it: yield from gen_obj_desc(el, depth+1, visited_ids.child())
  yield (-1, close)


def repr_clean(obj:Any) -> str:
  r = repr(obj)
  if isinstance(obj, (bytes,str,list,dict,set)) or _decent_repr_re.fullmatch(r): return r
  return f'{type(obj).__name__}({r})'

_decent_repr_re = re.compile(r'[a-zA-Z][.\w]*\(.*\)')


def repr_lim(obj:Any, limit=64) -> str:
  r = repr(obj)
  if len(r) <= limit: return r
  return r[:limit-1] + '…'
