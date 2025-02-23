# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from functools import reduce
from operator import or_


def idx_mask_for_range(range:range) -> int:
  '''
  Given a range of integers, return a bitmask with the bits set for the elements of the range.
  '''
  if not range:
    return 0
  assert range.start >= 0, range
  if range.step == 1:
    return ((1<<range.stop) - 1) - ((1<<range.start) - 1)
  else:
    return reduce(or_, (1<<i for i in range), 0)


def idx_ranges_for_mask(mask:int) -> list[range]:
  '''
  Given a bitmask, return a list of ranges of contiguous set bits.
  '''
  ranges = []
  start = None
  length = mask.bit_length()
  for i in range(length):
    is_set = (1<<i) & mask
    if is_set and start is None:
      start = i
    elif not is_set and start is not None:
      ranges.append(range(start, i))
      start = None
  if start is not None:
    ranges.append(range(start, length))
  return ranges


def idx_mask_for_length(length:int) -> int:
  '''
  Given a bit length, return the mask representing all the bits set in that length.
  '''
  return (1<<length) - 1
