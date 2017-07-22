# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from collections import defaultdict
from enum import Enum
from itertools import tee
from operator import le
from typing import Any, Callable, DefaultDict, Dict, Hashable, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple, TypeVar, Union
from .type_util import Comparable


T = TypeVar('T')
K = TypeVar('K', bound=Hashable)
V = TypeVar('V')
C = TypeVar('C', bound=Comparable)
CK = TypeVar('CK', bound=Comparable)


def is_sorted(iterable: Iterable, cmp=le) -> bool:
  'Test whether `iterable` is sorted according to `cmp` (default = `operator.le`).'
  a, b = tee(iterable)
  next(b, None) # map works like zip: stops as soon as any input is exhausted. The default `None` is ignored here.
  return all(map(cmp, a, b))


def first_el(iterable: Iterable[T]) -> T:
  'Advance `iterable` and return the first element or raise `ValueError`.'
  for el in iterable: return el
  raise ValueError('empty iterable')


def iter_from(iterable: Iterable[T], start: int) -> Iterator[T]:
  'Return an iterator over `iterable` that skips elements up to `start` index.'
  it = iter(iterable)
  c = start
  while c > 0:
    try: next(it)
    except StopIteration: break
    c -= 1
  return it


def extent(iterable: Iterable[C], key: Callable[[C], CK]=None, default: Optional[C]=None) -> Tuple[C, C]:
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


def count_by_pred(iterable: Iterable[T], pred: Callable[[T], Any]) -> int:
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
    if isinstance(el, range): return (el.start, el.stop) # type: ignore # mypy bug: "range" has no attribute "start"
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


def filtermap_with_mapping(iterable: Iterable[K], mapping: Mapping[K, V]) -> Iterable[V]:
  'Map the values of `iterable` through the mapping, dropping any elements not in the mapping.'
  for el in iterable:
    try: yield mapping[el]
    except KeyError: pass


def fan_by_index_fn(iterable: Iterable[T], index: Callable[[T], int], min_len=0) -> List[List[T]]:
  '''
  Fan out `iterable` into a list of lists, with a minimum length of `min_len`,
  according to the index returned by applying `index` to each element.
  '''
  l: List[List[T]] = []
  while len(l) < min_len:
    l.append([])
  for el in iterable:
    i = int(index(el))
    if i < 0: raise IndexError(i)
    while len(l) <= i:
      l.append([])
    l[i].append(el)
  return l


def fan_by_pred(iterable: Iterable[T], pred: Callable[[T], bool]) -> Tuple[List[T], List[T]]:
  'Fan out `iterable` into a pair of lists by applying `pred` to each element.'
  fan: Tuple[List[T], List[T]] = ([], [])
  for el in iterable:
    if pred(el):
      fan[1].append(el)
    else:
      fan[0].append(el)
  return fan


def fan_by_key_fn(iterable: Iterable[T], key: Callable[[T], K]) -> Dict[K, List[T]]:
  '''
  Fan out `iterable` into a dictionary by applying a function `key` that returns a group key for each element.
  returns a dictionary of lists.
  '''
  groups: Dict[K, List[T]] = {}
  for el in iterable:
    k = key(el)
    try:
      group = groups[k]
    except KeyError:
      group = []
      groups[k] = group
    group.append(el)
  return groups


def group_sorted_by_cmp(iterable: Iterable[T], cmp: Callable[[T, T], bool]) -> List[List[T]]:
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


def group_by_heads(iterable: Iterable[T], is_head: Callable[[T], bool], headless=OnHeadless.error) -> Iterable[List[T]]:
  '''
  Group elements of `iterable` by creating a new group every time the `is_head` predicate evaluates to true.
  If the first element of the stream is not a head, the behavior is specified by `headless`.
  '''
  it = iter(iterable)
  group: List[T] = []
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


def window_iter(iterable: Iterable[T], width=2) -> Iterator[Tuple[T, ...]]:
  'Yield tuples of the specified `width` (default 2), consisting of adjacent elements in `seq`.'
  assert width > 0
  buffer = []
  for el in iterable:
    buffer.append(el)
    if len(buffer) == width:
      yield tuple(buffer)
      del buffer[0]


def window_pairs(iterable, tail=None) -> Iterator[Tuple[T, T]]:
  it = iter(iterable)
  try: head = next(it)
  except StopIteration: return
  for el in it:
    yield (head, el)
    head = el
  yield (head, tail)


KTerminator = TypeVar('KTerminator', bound=Hashable)
PrefixTree = Dict[Union[K, KTerminator], Optional[Dict]] # mypy cannot handle recursive types.


def prefix_tree(iterables: Iterable[Sequence[K]], index=0, terminator=None) -> PrefixTree:
  'Make a nested mapping indicating shared prefixes of `iterables`.'
  d: Dict = {}
  subsets: DefaultDict = defaultdict(list)
  # partition the sequences by leading element.
  for seq in iterables:
    l = len(seq)
    assert l >= index
    if l  == index: # handle the terminal case immediately.
      d[terminator] = None
    else:
      subsets[seq[index]].append(seq)
  # recurse for each partition.
  for el, subset in subsets.items():
    d[el] = prefix_tree(subset, index=index + 1, terminator=terminator)
  return d

