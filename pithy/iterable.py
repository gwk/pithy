# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from enum import Enum
from io import IOBase
from itertools import tee
from operator import le
from random import shuffle
from typing import Any, Callable, Hashable, Iterable, Iterator, Mapping, Optional, TypeVar, Union

from .types import Comparable


_T = TypeVar('_T')
_K = TypeVar('_K', bound=Hashable)
_V = TypeVar('_V')
_R = TypeVar('_R')
_C = TypeVar('_C', bound=Comparable)
_CK = TypeVar('_CK', bound=Comparable)


class MultipleElements(ValueError):
  'Raised when an iterable unexpectedly has multiple elements.'


class NoElements(KeyError):
  'Raised when an iterable unexpectedly has no elements.'


known_leaf_types = (bool, bytearray, bytes, complex, float, int, str, type(None), type(Ellipsis), range, IOBase)
#^ Note: the only type that is strictly necessary is `str`, because its element type is `str` which causes infinite recursion.
# It also makes sense not to iterate over byte values or range indices, as that is probably not the intent of a generic iteration.
# Iterating over files is problematic, particularly because some are write-only and will fail.
# The remaining members are a speculative optimization.


def is_sorted(iterable: Iterable, cmp=le) -> bool:
  'Test whether `iterable` is sorted according to `cmp` (default = `operator.le`).'
  a, b = tee(iterable)
  next(b, None) # map works like zip: stops as soon as any input is exhausted. The default `None` is ignored here.
  return all(map(cmp, a, b))


def first_el(iterable: Iterable[_T]) -> _T:
  'Advance `iterable` and return the first element or raise `ValueError`.'
  for el in iterable: return el
  raise NoElements(iterable)


def single_el(iterable:Iterable[_T]) -> _T:
  first = init = object()
  for el in iterable:
    if first == init:
      first = el
    else:
      raise MultipleElements((first, el))
  if first == init: raise NoElements(iterable)
  return first # type: ignore[return-value]


def iter_from(iterable: Iterable[_T], start: int) -> Iterator[_T]:
  'Return an iterator over `iterable` that skips elements up to `start` index.'
  it = iter(iterable)
  c = start
  while c > 0:
    try: next(it)
    except StopIteration: break
    c -= 1
  return it


def iter_interleave_sep(iterable: Iterable[_T], sep: _T) -> Iterator[_T]:
  'Yield the elements of `iterable`, interleaving `sep` between elements.'
  it = iter(iterable)
  try: yield next(it)
  except StopIteration: return
  for el in it:
    yield sep
    yield el


def iter_unique(iterable: Iterable[_T]) -> Iterator[_T]:
  'Drop repeated elements, like unix `uniq`. TODO: rename to `iter_drop_repeated`.'
  prev:Any = object()
  for el in iterable:
    if el != prev:
      yield el
      prev = el


def iter_values(obj:Any) -> Iterator[Any]:
  if isinstance(obj, known_leaf_types): return
  if hasattr(obj, 'values'): # Treat as a mapping.
    yield from obj.values()
  else:
    try: it = iter(obj)
    except TypeError: return
    yield from it


def joinS(joiner:str, iterable:Iterable) -> str:
  'Join str representations, separated by `joiner`.'
  return joiner.join(map(str, iterable))

def joinSC(iterable:Iterable) -> str:
  'Join str representations, separated by comma.'
  return ','.join(map(str, iterable))

def joinSCS(iterable:Iterable) -> str:
  'Join str representations, separated by comma-space.'
  return ', '.join(map(str, iterable))

def joinST(iterable:Iterable) -> str:
  'Join str representations, separated by tab.'
  return '\t'.join(map(str, iterable))


def joinR(joiner:str, iterable:Iterable) -> str:
  'Join repr representations, separated by `joiner`.'
  return joiner.join(map(repr, iterable))

def joinRC(iterable:Iterable) -> str:
  'Join repr representations, separated by comma.'
  return ','.join(map(repr, iterable))

def joinRCS(iterable:Iterable) -> str:
  'Join repr representations, separated by comma-space.'
  return ', '.join(map(repr, iterable))

def joinRT(iterable:Iterable) -> str:
  'Join repr representations, separated by tab.'
  return '\t'.join(map(repr, iterable))


def extent(iterable: Iterable[_C], key: Callable[[_C], _CK]|None=None, default:_C|None=None) -> tuple[_C, _C]:
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


def closed_int_intervals(iterable: Iterable[int]) -> Iterable[tuple[int, int]]:
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


_RangeTypes = Union[int, range, tuple[int, int]]

def int_tuple_ranges(iterable: Iterable[_RangeTypes]) -> Iterable[tuple[int, int]]:
  'Given `iterable`, yield range pair tuples.'

  def pair_for_el(el: _RangeTypes) -> tuple[int, int]:
    if isinstance(el, range): return (el.start, el.stop)
    if isinstance(el, int): return (el, el + 1)
    assert isinstance(el, tuple)
    if len(el) != 2: raise ValueError(el)
    return el

  it = iter(iterable)
  try: low, end = pair_for_el(next(it))
  except StopIteration: return
  for el in it:
    l, e = pair_for_el(el)
    if e < l: raise ValueError(el)
    if l < end: raise ValueError('int_tuple_ranges requires monotonically increasing elements', end, l)
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


def fan_by_index_fn(iterable: Iterable[_T], index: Callable[[_T], int], min_len=0) -> list[list[_T]]:
  '''
  Fan out `iterable` into a list of lists, with a minimum length of `min_len`,
  according to the index returned by applying `index` to each element.
  '''
  l: list[list[_T]] = []
  while len(l) < min_len:
    l.append([])
  for el in iterable:
    i = int(index(el))
    if i < 0: raise IndexError(i)
    while len(l) <= i:
      l.append([])
    l[i].append(el)
  return l


def fan_by_pred(iterable: Iterable[_T], pred: Callable[[_T], bool]) -> tuple[list[_T], list[_T]]:
  'Fan out `iterable` into a pair of lists by applying `pred` to each element.'
  fan: tuple[list[_T], list[_T]] = ([], [])
  for el in iterable:
    if pred(el):
      fan[1].append(el)
    else:
      fan[0].append(el)
  return fan


def fan_by_key_fn(iterable:Iterable[_T], key:Callable[[_T],_K]) -> dict[_K, list[_T]]:
  '''
  Fan out `iterable` into a dictionary by applying a function `key` that returns a group key for each element.
  returns a dictionary of lists.
  '''
  groups: dict[_K, list[_T]] = {}
  for el in iterable:
    k = key(el)
    try:
      group = groups[k]
    except KeyError:
      group = []
      groups[k] = group
    group.append(el)
  return groups


def fan_items(iterable:Iterable[tuple[_K,_V]]) -> dict[_K,list[_V]]:
  '''
  Fan out `iterable` of key/value pair itmems into a dictionary of lists of values.
  '''
  groups:dict[_K,list[_V]] = {}
  for k, v in iterable:
    try: group = groups[k]
    except KeyError: groups[k] = group = []
    group.append(v)
  return groups


def fan_by_key_fn_and_transform(iterable:Iterable[_T], key:Callable[[_T],_K], transform:Callable[[_T],_R]) -> dict[_K, list[_R]]:
  '''
  Fan out `iterable` into a dictionary by applying a function `key` that returns a group key for each element,
  applying `transform` to each element.
  returns a dictionary of lists of transformed elements.
  '''
  groups: dict[_K, list[_R]] = {}
  for el in iterable:
    k = key(el)
    try:
      group = groups[k]
    except KeyError:
      group = []
      groups[k] = group
    group.append(transform(el))
  return groups


def group_by_cmp(iterable: Iterable[_T], cmp: Callable[[_T, _T], bool]) -> Iterable[list[_T]]:
  '''
  Group elements `iterable`, which must already be sorted,
  by applying the `comparison` predicate to each consecutive pair of elements.
  Consecutive elements for which the predicate returns truthy will be grouped together;
  a group is yielded whenever comparison fails.
  '''
  # TODO: convert to generator.
  it = iter(iterable)
  try: first = next(it)
  except StopIteration: return
  group = [first]
  prev = first
  for el in it:
    if cmp(prev, el):
      group.append(el)
    else:
      yield group
      group = [el]
    prev = el
  yield group


def group_by_key_fn(iterable:Iterable[_T], key:Callable[[_T], Comparable]) -> Iterable[list[_T]]:
  '''
  Group elements of `iterable`, which must already be sorted,
  by applying the `key` function to each element.
  Consecutive elements for which the key values are equal will be grouped together;
  a group is yielded whenever comparison fails.
  Unlike `itertools.groupby`, this function yields only the values, not the key/value pairs.
  '''
  it = iter(iterable)
  try: first = next(it)
  except StopIteration: return
  group = [first]
  prev_key = key(first)
  for el in it:
    curr_key = key(el)
    if curr_key == prev_key:
      group.append(el)
    else:
      yield group
      group = [el]
    prev_key = curr_key
  yield group


def group_by_attr(iterable:Iterable[_T], attr:str) -> Iterable[list[_T]]:
  '''
  Group elements of `iterable`, which must already be sorted,
  by comparing the `attr` attribute of each element.
  Consecutive elements for which the attribute values are equal will be grouped together;
  a group is yielded whenever comparison fails.
  '''
  it = iter(iterable)
  try: first = next(it)
  except StopIteration: return
  group = [first]
  prev_val = getattr(first, attr)
  for el in it:
    curr_val = getattr(el, attr)
    if curr_val == prev_val:
      group.append(el)
    else:
      yield group
      group = [el]
    prev_val = curr_val
  yield group


class OnHeadless(Enum):
  error, drop, keep = range(3)


def group_by_heads(iterable: Iterable[_T], is_head: Callable[[_T], bool], headless=OnHeadless.error, keep_heads=True) \
 -> Iterator[list[_T]]:
  '''
  Group elements of `iterable` by creating a new group every time the `is_head` predicate evaluates to true.
  If the first element of the stream is not a head, the behavior is specified by `headless`.
  '''
  it = iter(iterable)
  group: list[_T] = []
  while True: # consume all headless (leading tail) tokens.
    try: el = next(it)
    except StopIteration:
      if group: yield group # Headless.keep.
      return
    if is_head(el):
      if group: # Headless.keep.
        yield group
        group = []
      if keep_heads: group.append(el)
      break
    else: # leading tail element.
      if headless == OnHeadless.error: raise ValueError(el)
      if headless == OnHeadless.drop: continue
      if headless == OnHeadless.keep: group.append(el)
      else: raise TypeError(headless)
  for el in it:
    if is_head(el):
      yield group
      group = [el] if keep_heads else []
    else:
      group.append(el)
  if group: yield group


def set_from(iterables:Iterable[Iterable[_K]]) -> set[_K]:
  s:set[_K] = set()
  for el in iterables:
    s.update(el)
  return s


def frozenset_from(iterables:Iterable[Iterable[_K]]) -> frozenset[_K]:
  return frozenset(set_from(iterables))


def split_els(iterable:Iterable[_T], split=Callable[[_T], Optional[tuple[_T, _T]]]) -> Iterator[_T]:
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


def split_by_preds(iterable: Iterable[_T], *preds: Callable[[_T], bool]) -> Iterable[tuple[bool, list[_T]]]:
  '''
  Split the sequence whenever the sequence of predicates has consecutively matched.
  Each yielded chunk is a pair (is_split_seq, seq).
  For example:
  `split_by_preds('abcde', lambda el: el=='b', lambde el: el=='c')` yields:
  * (False, ['a'])
  * (True, ['b', 'c'])
  * (False, ['d', 'e'])
  '''
  if not preds: raise ValueError('split_by_preds requires at least one predicate')
  l = len(preds)
  buffer: list[_T] = []
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


def transpose(iterable: Iterable[Iterable[_T]]) -> Iterable[list[_T]]:
  return map(list, zip(*iterable))


def window_iter(iterable: Iterable[_T], width=2) -> Iterator[tuple[_T, ...]]:
  'Yield tuples of the specified `width` (default 2), consisting of adjacent elements in `seq`.'
  # TODO: use tee? might be faster.
  assert width > 0
  buffer = []
  for el in iterable:
    buffer.append(el)
    if len(buffer) == width:
      yield tuple(buffer)
      del buffer[0]


def window_pairs(iterable: Iterable[_T], tail: _T|None=None) -> Iterator[tuple[_T, Optional[_T]]]:
  'Yield pairs of adjacent elements in `seq`, including a final pair consisting of the last element and `tail`.'
  it = iter(iterable)
  try: head = next(it)
  except StopIteration: return
  for el in it:
    yield (head, el)
    head = el
  yield (head, tail)


_PrefixTreeTerminator = TypeVar('_PrefixTreeTerminator', bound=Hashable)
PrefixTree = dict[Union[_K, _PrefixTreeTerminator], Optional[dict]] # mypy cannot handle recursive types.


def prefix_tree(iterables:Iterable[Iterable[_K]], terminator:_PrefixTreeTerminator|None=None, update:PrefixTree|None=None) -> PrefixTree:
  '''
  Generate a simple prefix tree from the given iterables.
  The `terminator` key is used to mark the end of a sequence; it defaults to None.
  The result is a nested dictionary.
  If `terminator` is present it marks the end of a complete sequence.
  All other keys point to subdictionaries with that prefix.
  '''
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


def shuffled(iterable:Iterable[_T]) -> list[_T]:
  '''
  Return a shuffled list of `iterable`.
  '''
  l = list(iterable)
  shuffle(l)
  return l
