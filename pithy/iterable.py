# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from collections import defaultdict
from enum import Enum
from itertools import tee
from operator import le
from typing import cast, Callable, DefaultDict, Dict, Hashable, Iterable, Iterator, List, Sequence, Tuple, TypeVar, Union

T = TypeVar('T')
K = TypeVar('K', bound=Hashable)


def is_sorted(iterable: Iterable, cmp=le) -> bool:
  'Test whether `iterable` is sorted according to `cmp` (default = `operator.le`).'
  a, b = tee(iterable)
  next(b, None) # map works like zip: stops as soon as any input is exhausted. The default `None` is ignored here.
  return all(map(cmp, a, b))


def first_el(iterable: Iterable[T]) -> T:
  'Advance `iterable` and return the first element or raise `ValueError`.'
  for el in iterable: return el
  raise ValueError('empty iterable')


def iter_from(iterable: Iterable[T], start) -> Iterator[T]:
  'Return an iterator over `iterable` that skips elements up to `start` index.'
  it = iter(iterable)
  c = start
  while c > 0:
    try: next(it)
    except StopIteration: break
    c -= 1
  return it


def seq_int_closed_intervals(iterable: Iterable[int]) -> Iterable[Tuple[int, int]]:
  'Given `iterable` of integers, yield a sequence of closed intervals.'
  it = iter(iterable)
  try: first = next(it)
  except StopIteration: return
  if not isinstance(first, int):
    raise TypeError('seq_int_closed_intervals requires a sequence of int elements; received first element: {!r}', first)
  interval = (first, first)
  for i in it:
    l, h = interval
    if i < h:
      raise ValueError('seq_int_closed_intervals requires monotonically increasing elements')
    if i == h: continue
    if i == h + 1:
      interval = (l, i)
    else:
      yield interval
      interval = (i, i)
  yield interval


_RangeTypes = Union[int, range, Tuple[int, int]]
def seq_int_ranges(iterable: Iterable[_RangeTypes]) -> Iterable[Tuple[int, int]]:
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


def fan_seq_by_index(iterable: Iterable[T], index: Callable[[T], int], min_len=0) -> List[List[T]]:
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


def fan_seq_by_pred(iterable: Iterable[T], pred: Callable[[T], bool]) -> Tuple[List[T], List[T]]:
  'Fan out `seq` into a pair of lists by applying `pred` to each element.'
  fan: Tuple[List[T], List[T]] = ([], [])
  for el in iterable:
    if pred(el):
      fan[1].append(el)
    else:
      fan[0].append(el)
  return fan


def fan_seq_by_key(iterable: Iterable[T], key: Callable[[T], K]) -> Dict[K, List[T]]:
  '''
  Fan out `seq` into a dictionary by applying a function `key` that returns a group key for each element.
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


def fan_sorted_seq_by_cmp(iterable: Iterable[T], cmp: Callable[[T, T], bool]) -> List[List[T]]:
  '''
  Fan out `seq`, which must already be sorted,
  by applying the `comparison` predicate to each consecutive pair of elements.
  Group the elements of the sorted sequence by applying a comparison predicate
  to each successive pair of elements, creating a new group when the comparison fails.
  '''
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


def group_seq_by_heads(seq: Iterable[T], is_head: Callable[[T], bool], headless=OnHeadless.error) -> Iterable[T]:
  it = iter(seq)
  group = [] # type: ignore
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


def window_seq(seq: Iterable[T], width=2) -> Iterator[Tuple[T, ...]]:
  'Yield tuples of the specified `width` (default 2), consisting of adjacent elements in `seq`.'
  assert width > 0
  buffer = []
  for el in seq:
    buffer.append(el)
    if len(buffer) == width:
      yield tuple(buffer)
      del buffer[0]


def window_seq_pairs(seq, tail=None) -> Iterator[Tuple[T, T]]:
  it = iter(seq)
  try: head = next(it)
  except StopIteration: return
  for el in it:
    yield (head, el)
    head = el
  yield (head, tail)


def seq_prefix_tree(iterables: Iterable[Sequence[T]], index=0, terminator=None) -> Dict:
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
    d[el] = seq_prefix_tree(subset, index=index + 1, terminator=terminator)
  return d

