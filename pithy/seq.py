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


def seq_from_index(seq, start_index):
  'Returns an iterator for the sequence that skips elements up to the start_index.'
  it = iter(seq)
  c = start_index
  while c > 0:
    try: next(it)
    except StopIteration: break
    c -= 1
  return it


def group_seq_by_index(seq, index, len=0):
  l = DefaultList(list, len=len)
  for el in seq:
    i = int(index(el))
    if i < 0: raise IndexError(i)
    l[i].append(el)
  return l


def grouped_seq(seq, key):
  '''
  Group the elements of the sequence by applying a function `key` that returns a group key for each element.
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

def grouped_sorted_seq(seq, comparison):
  '''
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

def windowed(seq, length=2):
  'Yield tuples of the specified length (default 2), consisting of adjacent elements in sequence.'
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


