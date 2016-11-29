# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# TODO: rename to something less common.

from collections import defaultdict
from enum import Enum
from typing import Callable, Iterable


class DefaultList(list):
  '''
  A subclass of `list` that adds default elements produced by a factory function
  when an out-of-bounds element is accessed.
  '''

  def __init__(self, factory, seq=[], len=0):
    super().__init__(seq)
    self.factory = factory
    for i in range(0, len):
      self.append(self.factory())

  def __getitem__(self, index):
    while len(self) <= index:
      self.append(self.factory())
    return super().__getitem__(index)

  def __repr__(self):
    return '{}({}, {})'.format(type(self).__qualname__, self.factory, super().__repr__())


def seq_first(seq):
  for el in seq: return el
  raise ValueError('empty sequence')


def seq_from_index(seq, start_index):
  'Returns an iterator for the sequence that skips elements up to the start_index.'
  it = iter(seq)
  c = start_index
  while c > 0:
    try: next(it)
    except StopIteration: break
    c -= 1
  return it


def seq_int_closed_intervals(seq):
  'Given a sequence of integers, yield a sequence of closed intervals.'
  it = iter(seq)
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


def seq_int_ranges(seq):
  'Given a mixed sequence of ints, int ranges, and int pairs, yield a sequence of range pair tuples.'

  def pair_for_el(el):
    if isinstance(el, range): return (el.start, el.stop)
    if isinstance(el, int): return (el, el + 1)
    if not isinstance(el, tuple) or len(el) != 2: raise ValueError(el)
    return el

  it = iter(seq)
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


def fan_seq_by_index(seq, index, min_len=0):
  '''
  Fan out `seq` into a list of lists, with a minimum length of `min_len`,
  according to the index returned by applying `index` to each element.
  '''
  l = []
  while len(l) < min_len:
    l.append([])
  for el in seq:
    i = int(index(el))
    if i < 0: raise IndexError(i)
    while len(l) <= i:
      l.append([])
    l[i].append(el)
  return l


def fan_seq_by_pred(seq, pred):
  'Fan out `seq` into a pair of lists by applying `pred` to each element.'
  fan = ([], [])
  for el in seq:
    i = int(pred(el))
    if i < 0: raise IndexError(i)
    fan[i].append(el)
  return fan


def fan_seq_by_key(seq, key):
  '''
  Fan out `seq` into a dictionary by applying a function `key` that returns a group key for each element.
  returns a dictionary of arrays.
  '''
  groups = {}
  for el in seq:
    k = key(el)
    try:
      group = groups[k]
    except KeyError:
      group = []
      groups[k] = group
    group.append(el)
  return groups


def fan_sorted_seq_by_comp(seq, comparison):
  # TODO: rename group.
  '''
  Fan out `seq`, which must already be sorted,
  by applying the `comparison` predicate to each consecutive pair of elements.
  Group the elements of the sorted sequence by applying a comparison predicate
  to each successive pair of elements, creating a new group when the comparison fails.
  '''
  it = iter(seq)
  try:
    first = next(it)
  except StopIteration:
    return []
  groups = []
  group = [first]
  prev = first
  for el in it:
    if comparison(prev, el):
      group.append(el)
    else:
      groups.append(group)
      group = [el]
    prev = el
  if group:
    groups.append(group)
  return groups


class HeadlessMode(Enum):
  error, drop, keep = range(3)


def group_seq_by_heads(seq: Iterable, is_head: Callable, headless=HeadlessMode.error) -> Iterable:
  it = iter(seq)
  group = [] # type: ignore.
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
      if headless == HeadlessMode.error: raise ValueError(el)
      if headless == headless.drop: continue
      if headless == headless.keep: group.append(el)
      else: raise TypeError(headless)
  for el in it:
    if is_head(el):
      yield group
      group = [el]
    else:
      group.append(el)
  if group: yield group


def window_seq(seq, width=2):
  'Yield tuples of the specified `width` (default 2), consisting of adjacent elements in `seq`.'
  assert length > 0
  buffer = []
  for el in seq:
    buffer.append(el)
    if len(buffer) == length:
      yield tuple(buffer)
      del buffer[0]


def window_seq_pairs(seq, tail=None):
  it = iter(seq)
  try: head = next(it)
  except StopIteration: return
  for el in it:
    yield (head, el)
    head = el
  yield (head, tail)


def seq_prefix_tree(seq_set, index=0, terminator=None):
  'Make a nested mapping indicating shared prefixes from a set of sequences.'
  d = {}
  subsets = defaultdict(list)
  # partition the sequences by leading element.
  for seq in seq_set:
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


_raise = object()

class IterBuffer():
  '''
  Iterable object that buffers an iterable.
  Call push() to push an item into the buffer;
  this will be returned on the subsequent call to next().
  '''


  def __init__(self, iterable):
    self.iterator = iter(iterable)
    self.buffer = []


  def __repr__(self):
    return 'IterBuffer({!r}, buffer={!r})'.format(self.iterator, self.buffer)


  def __iter__(self): return self


  def __next__(self):
    try: return self.buffer.pop()
    except IndexError: pass
    return next(self.iterator)


  def push(self, item):
    self.buffer.append(item)


  def peek(self, default=_raise):
    try: return self.buffer[-1]
    except IndexError: pass
    try: el = next(self.iterator)
    except StopIteration:
      if default is _raise: raise
      else: return default
    self.buffer.append(el)
    return el


  def take_while(self, predicate):
    for el in self:
      if predicate(el):
        yield el
      else:
        self.buffer.append(el)
        break


  def drop_while(self, predicate):
    for el in self:
      if not predicate(el):
        self.buffer.append(el)
        break


  def peek_while(self, predicate):
    els = list(self.take_while(predicate))
    self.buffer.extend(reversed(els))
    return els


  def take(self, count, short=False, default=_raise):
    els = []
    for _ in range(count):
      try: els.append(next(self))
      except StopIteration:
        if short: break
        if default is _raise: raise
        els.append(default)
    return els


  def peeks(self, count, short=False, default=_raise):
    if 0 < count <= len(self.buffer):
      return reversed(self.buffer[-count:])
    els = []
    for _ in range(count):
      try: els.append(self.next())
      except StopIteration:
        if short: break
        if default is _raise: raise
        els.append(default)
    self.buffer.extend(reversed(els))
    return els


  @property
  def is_live(self):
    try: self.peek()
    except StopIteration: return False
    else: return True
