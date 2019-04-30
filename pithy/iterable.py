# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from collections import defaultdict
from enum import Enum
from functools import singledispatch
from itertools import tee
from operator import le
from typing import (Any, Callable, DefaultDict, Dict, FrozenSet, Hashable, Iterable, Iterator, List, Mapping, Optional,
  Sequence, Set, Tuple, TypeVar, Union)

from .types import Comparable


_T = TypeVar('_T')
_K = TypeVar('_K', bound=Hashable)
_V = TypeVar('_V')
_C = TypeVar('_C', bound=Comparable)
_CK = TypeVar('_CK', bound=Comparable)


# Note: the only type that is strictly necessary is `str`, because its element type is `str` which causes infinite recursion.
# It also makes sense not to iterate over byte values or range indices, as that is probably not the intent of a generic iteration.
# The remaining members are a speculative optimization.
known_leaf_types = (bool, bytearray, bytes, complex, float, int, str, range, type(None), type(Ellipsis))



def is_sorted(iterable: Iterable, cmp=le) -> bool:
  'Test whether `iterable` is sorted according to `cmp` (default = `operator.le`).'
  a, b = tee(iterable)
  next(b, None) # map works like zip: stops as soon as any input is exhausted. The default `None` is ignored here.
  return all(map(cmp, a, b))


def first_el(iterable: Iterable[_T]) -> _T:
  'Advance `iterable` and return the first element or raise `ValueError`.'
  for el in iterable: return el
  raise ValueError('empty iterable')


def iter_from(iterable: Iterable[_T], start: int) -> Iterator[_T]:
  'Return an iterator over `iterable` that skips elements up to `start` index.'
  it = iter(iterable)
  c = start
  while c > 0:
    try: next(it)
    except StopIteration: break
    c -= 1
  return it


def iter_unique(iterable: Iterable[_T]) -> Iterator[_T]:
  'Drop repeated elements, like unix `uniq`. TODO: rename to `iter_drop_repeated`.'
  prev:Any = object()
  for el in iterable:
    if el != prev:
      yield el
      prev = el


@singledispatch
def iter_values(obj:Any) -> Iterator[Any]:
  if isinstance(obj, known_leaf_types): return

  if hasattr(obj, 'values'): # Treat as a mapping.
    yield from obj.values()

  try: it = iter(obj)
  except TypeError: return
  yield from it




def extent(iterable: Iterable[_C], key: Callable[[_C], _CK]=None, default: Optional[_C]=None) -> Tuple[_C, _C]:
  'Return the min and max.'
  it = iter(iterable)
  first = next(it) if default is None else next(it, default)
  l = first
  h = first
  if key is None:
    for el in it:
      if el < l:
        l = el
      if h < el:
        h = el
  else:
    kl = key(l)
    kh = key(h)
    for el in it:
      k = key(el)
      if k < kl:
        l = el
        kl = k
      if kh < k:
        h = el
        kh = k
  return (l, h)


def count_by_pred(iterable: Iterable[_T], pred: Callable[[_T], Any]) -> int:
  count = 0
  for el in iterable:
    if pred(el): count += 1
  return count


def closed_int_intervals(iterable: Iterable[int]) -> Iterable[Tuple[int, int]]:
  'Given `iterable` of integers, yield a sequence of closed intervals.'
  it = iter(iterable)
  try: first = next(it)
  except StopIteration: return
  if not isinstance(first, int):
    raise TypeError('closed_int_intervals requires a sequence of int elements; received first element: {!r}', first)
  interval = (first, first)
  for i in it:
    l, h = interval
    if i < h:
      raise ValueError('closed_int_intervals requires monotonically increasing elements')
    if i == h: continue
    if i == h + 1:
      interval = (l, i)
    else:
      yield interval
      interval = (i, i)
  yield interval


_RangeTypes = Union[int, range, Tuple[int, int]]
def int_tuple_ranges(iterable: Iterable[_RangeTypes]) -> Iterable[Tuple[int, int]]:
  'Given `iterable`, yield range pair tuples.'

  def pair_for_el(el: _RangeTypes) -> Tuple[int, int]:
    if isinstance(el, range): return (el.start, el.stop)
    if isinstance(el, int): return (el, el + 1)
    if not isinstance(el, tuple) or len(el) != 2: raise ValueError(el)
    return el

  it = iter(iterable)
  try: low, end = pair_for_el(next(it))
  except StopIteration: return
  for el in it:
    l, e = pair_for_el(el)
    if e < l: raise ValueError(el)
    if l < end: raise ValueError('seq_int_ranges requires monotonically increasing elements', end, l)
    if l == end:
      end = e
    else:
      yield (low, end)
      low = l
      end = e
  yield (low, end)


def filtermap_with_mapping(iterable: Iterable[_K], mapping: Mapping[_K, _V]) -> Iterable[_V]:
  'Map the values of `iterable` through the mapping, dropping any elements not in the mapping.'
  for el in iterable:
    try: yield mapping[el]
    except KeyError: pass


def fan_by_index_fn(iterable: Iterable[_T], index: Callable[[_T], int], min_len=0) -> List[List[_T]]:
  '''
  Fan out `iterable` into a list of lists, with a minimum length of `min_len`,
  according to the index returned by applying `index` to each element.
  '''
  l: List[List[_T]] = []
  while len(l) < min_len:
    l.append([])
  for el in iterable:
    i = int(index(el))
    if i < 0: raise IndexError(i)
    while len(l) <= i:
      l.append([])
    l[i].append(el)
  return l


def fan_by_pred(iterable: Iterable[_T], pred: Callable[[_T], bool]) -> Tuple[List[_T], List[_T]]:
  'Fan out `iterable` into a pair of lists by applying `pred` to each element.'
  fan: Tuple[List[_T], List[_T]] = ([], [])
  for el in iterable:
    if pred(el):
      fan[1].append(el)
    else:
      fan[0].append(el)
  return fan


def fan_by_key_fn(iterable: Iterable[_T], key: Callable[[_T], _K]) -> Dict[_K, List[_T]]:
  '''
  Fan out `iterable` into a dictionary by applying a function `key` that returns a group key for each element.
  returns a dictionary of lists.
  '''
  groups: Dict[_K, List[_T]] = {}
  for el in iterable:
    k = key(el)
    try:
      group = groups[k]
    except KeyError:
      group = []
      groups[k] = group
    group.append(el)
  return groups


def group_sorted_by_cmp(iterable: Iterable[_T], cmp: Callable[[_T, _T], bool]) -> List[List[_T]]:
  '''
  Group elements `iterable`, which must already be sorted,
  by applying the `comparison` predicate to each consecutive pair of elements.
  Consecutive elements for which the predicate returns truthy will be grouped together;
  a group is yielded whenever comparison fails.
  '''
  # TODO: convert to generator.
  it = iter(iterable)
  try:
    first = next(it)
  except StopIteration:
    return []
  # TODO: rename group.
  groups = []
  group = [first]
  prev = first
  for el in it:
    if cmp(prev, el):
      group.append(el)
    else:
      groups.append(group)
      group = [el]
    prev = el
  if group:
    groups.append(group)
  return groups


class OnHeadless(Enum):
  error, drop, keep = range(3)


def group_by_heads(iterable: Iterable[_T], is_head: Callable[[_T], bool], headless=OnHeadless.error) -> Iterable[List[_T]]:
  '''
  Group elements of `iterable` by creating a new group every time the `is_head` predicate evaluates to true.
  If the first element of the stream is not a head, the behavior is specified by `headless`.
  '''
  it = iter(iterable)
  group: List[_T] = []
  while True: # consume all headless (leading tail) tokens.
    try: el = next(it)
    except StopIteration:
      if group: yield group
      return
    if is_head(el):
      if group:
        yield group
        group = []
      group.append(el)
      break
    else: # leading tail element.
      if headless == OnHeadless.error: raise ValueError(el)
      if headless == OnHeadless.drop: continue
      if headless == OnHeadless.keep: group.append(el)
      else: raise TypeError(headless)
  for el in it:
    if is_head(el):
      yield group
      group = [el]
    else:
      group.append(el)
  if group: yield group


def set_from(iterables:Iterable[Iterable[_K]]) -> Set[_K]:
  s:Set[_K] = set()
  for el in iterables:
    s.update(el)
  return s


def frozenset_from(iterables:Iterable[Iterable[_K]]) -> FrozenSet[_K]:
  return frozenset(set_from(iterables))


def split_els(iterable:Iterable[_T], split=Callable[[_T], Optional[Tuple[_T, _T]]]) -> Iterator[_T]:
  '''
  Repeatedly split the current element using the `split` function until it returns None.
  '''
  for el in iterable:
    r = split(el)
    while r is not None:
      head, el = r
      yield head
      r = split(el)
    yield el


def split_by_preds(iterable: Iterable[_T], *preds: Callable[[_T], bool]) -> Iterable[Tuple[bool, List[_T]]]:
  '''
  Split the sequence whenever the sequence of predicates has consecutively matched.
  Each yielded chunk is a pair (is_split_seq, seq).
  '''
  if not preds: raise ValueError('split_by_preds requires at least one predicate')
  l = len(preds)
  buffer: List[_T] = []
  for el in iterable:
    buffer.append(el)
    if len(buffer) >= l:
      tail = buffer[-l:]
      if all(p(e) for p, e in zip(preds, tail)):
        if len(buffer) > l:
          yield (False, buffer[:-l])
        yield (True, tail)
        buffer.clear()
  if buffer:
    yield (False, buffer)


def window_iter(iterable: Iterable[_T], width=2) -> Iterator[Tuple[_T, ...]]:
  'Yield tuples of the specified `width` (default 2), consisting of adjacent elements in `seq`.'
  assert width > 0
  buffer = []
  for el in iterable:
    buffer.append(el)
    if len(buffer) == width:
      yield tuple(buffer)
      del buffer[0]


def window_pairs(iterable: Iterable[_T], tail: Optional[_T]=None) -> Iterator[Tuple[_T, Optional[_T]]]:
  'Yield pairs of adjacent elements in `seq`, including a final pair consisting of the last element and `tail`.'
  it = iter(iterable)
  try: head = next(it)
  except StopIteration: return
  for el in it:
    yield (head, el)
    head = el
  yield (head, tail)


_PrefixTreeTerminator = TypeVar('_PrefixTreeTerminator', bound=Hashable)
PrefixTree = Dict[Union[_K, _PrefixTreeTerminator], Optional[Dict]] # mypy cannot handle recursive types.


def prefix_tree(iterables:Iterable[Iterable[_K]], terminator:_PrefixTreeTerminator=None, update:PrefixTree=None) -> PrefixTree:
  res:PrefixTree = {} if update is None else update
  for it in iterables:
    d = res
    for el in it:
      try:
        e = d[el]
        assert e is not None
        d = e
      except KeyError:
        e = {}
        d[el] = e
        d = e
    d[terminator] = None
  return res
