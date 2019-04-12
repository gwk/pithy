# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Sequence utilities.'


from bisect import bisect_left, bisect_right
from typing import Iterator, Sequence, Tuple, TypeVar


_T = TypeVar('_T')


def sorted_list_index(a: Sequence[_T], x: _T) -> int:
  '''
  Locate the leftmost value exactly equal to x.
  From stdlib bisect documentation.
  '''
  i = bisect_left(a, x)
  if i != len(a) and a[i] == x:
    return i
  raise ValueError


def sorted_list_find_lt(a: Sequence[_T], x: _T) -> _T:
  '''
  Find rightmost value less than x.
  From stdlib bisect documentation.
  '''
  i = bisect_left(a, x)
  if i:
    return a[i-1]
  raise ValueError


def sorted_list_find_le(a: Sequence[_T], x: _T) -> _T:
  '''
  Find rightmost value less than or equal to x.
  From stdlib bisect documentation.
  '''
  i = bisect_right(a, x)
  if i:
    return a[i-1]
  raise ValueError


def sorted_list_find_gt(a: Sequence[_T], x: _T) -> _T:
  '''
  Find leftmost value greater than x.
  From stdlib bisect documentation.
  '''
  i = bisect_right(a, x)
  if i != len(a):
    return a[i]
  raise ValueError


def sorted_list_find_ge(a: Sequence[_T], x: _T) -> _T:
  '''Find leftmost item greater than or equal to x.
  From stdlib bisect documentation.
  '''
  i = bisect_left(a, x)
  if i != len(a):
    return a[i]
  raise ValueError


def iter_pairs_of_el_is_last(seq:Sequence[_T]) -> Iterator[Tuple[_T, bool]]:
  last = len(seq) - 1
  return ((el, i==last) for i, el in enumerate(seq))
