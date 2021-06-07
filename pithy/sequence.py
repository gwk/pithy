# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Sequence utilities.'


from bisect import bisect_left, bisect_right
from typing import Iterator, Sequence, Tuple, TypeVar


_T = TypeVar('_T')


def seq_rindex(seq:Sequence[_T], el: _T) -> int:
  for i in range(len(seq) - 1, -1, -1):
    if seq[i] == el: return i
  raise ValueError(el)


def sorted_seq_index(seq:Sequence[_T], el:_T) -> int:
  '''
  Locate the leftmost element exactly equal to `el`.
  From stdlib bisect documentation.
  '''
  i = bisect_left(seq, el)
  if i != len(seq) and seq[i] == el:
    return i
  raise ValueError(el)


def sorted_seq_find_lt(seq:Sequence[_T], el:_T) -> _T:
  '''
  Find rightmost element less than `el`.
  From stdlib bisect documentation.
  '''
  i = bisect_left(seq, el)
  if i:
    return seq[i-1]
  raise ValueError


def sorted_seq_find_le(seq:Sequence[_T], el:_T) -> _T:
  '''
  Find rightmost element less than or equal to `el`.
  From stdlib bisect documentation.
  '''
  i = bisect_right(seq, el)
  if i:
    return seq[i-1]
  raise ValueError


def sorted_seq_find_gt(seq:Sequence[_T], el:_T) -> _T:
  '''
  Find leftmost element greater than `el`.
  From stdlib bisect documentation.
  '''
  i = bisect_right(seq, el)
  if i != len(seq):
    return seq[i]
  raise ValueError


def sorted_seq_find_ge(seq:Sequence[_T], el:_T) -> _T:
  '''Find leftmost element greater than or equal to `el`.
  From stdlib bisect documentation.
  '''
  i = bisect_left(seq, el)
  if i != len(seq):
    return seq[i]
  raise ValueError


def iter_pairs_of_el_is_last(seq:Sequence[_T]) -> Iterator[Tuple[_T, bool]]:
  last = len(seq) - 1
  return ((el, i==last) for i, el in enumerate(seq))
