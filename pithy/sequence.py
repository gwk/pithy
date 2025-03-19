# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Sequence utilities.'


from bisect import bisect_left, bisect_right
from typing import Sequence, TypeVar


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
  i = bisect_left(seq, el) # type: ignore[call-overload]
  if i != len(seq) and seq[i] == el:
    return i # type: ignore[no-any-return]
  raise ValueError(el)


def sorted_seq_find_lt(seq:Sequence[_T], el:_T) -> _T:
  '''
  Find rightmost element less than `el`.
  From stdlib bisect documentation.
  '''
  i = bisect_left(seq, el) # type: ignore[call-overload]
  if i:
    return seq[i-1] # type: ignore[no-any-return]
  raise ValueError


def sorted_seq_find_le(seq:Sequence[_T], el:_T) -> _T:
  '''
  Find rightmost element less than or equal to `el`.
  From stdlib bisect documentation.
  '''
  i = bisect_right(seq, el) # type: ignore[call-overload]
  if i:
    return seq[i-1] # type: ignore[no-any-return]
  raise ValueError


def sorted_seq_find_gt(seq:Sequence[_T], el:_T) -> _T:
  '''
  Find leftmost element greater than `el`.
  From stdlib bisect documentation.
  '''
  i = bisect_right(seq, el) # type: ignore[call-overload]
  if i != len(seq):
    return seq[i] # type: ignore[no-any-return]
  raise ValueError


def sorted_seq_find_ge(seq:Sequence[_T], el:_T) -> _T:
  '''Find leftmost element greater than or equal to `el`.
  From stdlib bisect documentation.
  '''
  i = bisect_left(seq, el) # type: ignore[call-overload]
  if i != len(seq):
    return seq[i] # type: ignore[no-any-return]
  raise ValueError


def dl_edit_distance(seq_a:Sequence[_T], seq_b:Sequence[_T]) -> int:
  '''
  Compute the Damerau-Levenshtein edit distance between two sequences.
  This is a generalization of the Levenshtein distance that allows for transpositions of adjacent characters.
  The algorithm is based on the one described in:
  https://en.wikipedia.org/wiki/Damerau%E2%80%93Levenshtein_distance
  '''
  la = len(seq_a)
  lb = len(seq_b)
  if la == 0: return lb
  if lb == 0: return la

  if la > lb:
    seq_a, seq_b = seq_b, seq_a # seq_a is the shorter sequence.
    la, lb = lb, la

  # Initialize the distance matrix.
  d = [[0] * (lb + 1) for _ in range(la + 1)]
  for i in range(la + 1): d[i][0] = i
  for j in range(lb + 1): d[0][j] = j

  # Compute the distance matrix.
  for i in range(1, la + 1):
    for j in range(1, lb + 1):
      cost = 0 if seq_a[i - 1] == seq_b[j - 1] else 1
      d[i][j] = min(
        d[i - 1][j] + 1, # Deletion
        d[i][j - 1] + 1, # Insertion
        d[i - 1][j - 1] + cost # Substitution
      )
      if i > 1 and j > 1 and seq_a[i - 1] == seq_b[j - 2] and seq_a[i - 2] == seq_b[j - 1]:
        d[i][j] = min(d[i][j], d[i - 2][j - 2] + cost)
  return d[la][lb]
