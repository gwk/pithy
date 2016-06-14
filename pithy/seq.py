# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


def seq_from_index(seq, start_index):
  it = iter(seq)
  c = start_index
  while c > 0:
    try:
      next(it)
      c -= 1
    except StopIteration:
      break
  return it


def grouped_seq(seq, key_fn):
  '''
  group the elements of the sequence by applying a function to each object that returns a key.
  returns a dictionary of arrays.
  '''
  groups = {}
  for el in seq:
    key = key_fn(el)
    try:
      group = groups[key]
    except KeyError:
      group = []
      groups[key] = group
    group.append(el)
  return groups

def grouped_sorted_seq(seq, comparison):
  '''
  group the elements of the sorted sequence by applying a comparison predicate
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

def zip_neighbors(seq, length=2):
  assert length > 0
  buffer = []
  for el in seq:
    buffer.append(el)
    if len(buffer) == length:
      yield tuple(buffer)
      del buffer[0]


class IterBuffer():
  
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


