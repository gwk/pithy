# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# TODO: rename to something less common.


class DefaultList(list):
  'A subclass of `list` that adds default elements produced by a factory function when an out-of-bounds element is accessed.'

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


def seq_int_intervals(seq):
  it = iter(seq)
  try: first = next(it)
  except StopIteration: return
  interval = (first, first)
  for i in it:
    l, h = interval
    if i < h:
      raise ValueError('seq_int_intervals requires monotonically increasing elements')
    if i == h: continue
    if i == h + 1:
      interval = (l, i)
    else:
      yield interval
      interval = (i, i)
  yield interval


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

def window_seq(seq, width=2):
  'Yield tuples of the specified `width` (default 2), consisting of adjacent elements in `seq`.'
  assert length > 0
  buffer = []
  for el in seq:
    buffer.append(el)
    if len(buffer) == length:
      yield tuple(buffer)
      del buffer[0]


class IterBuffer():
  '''
  Iterable object that buffers another iterator.
  Call push() to push an item into the buffer;
  this will be returned on the subsequent call to next().
  '''
  def __init__(self, iterator):
    self.iterator = iterator
    self.buffer = []

  def __iter__(self): return self

  def __next__(self):
    try:
      return self.buffer.pop()
    except IndexError: pass
    return next(self.iterator)

  def push(self, item):
    self.buffer.append(item)


