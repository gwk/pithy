# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from bisect import bisect
from typing import Dict, List, Optional, Sequence, TypeVar


_T = TypeVar('_T')

Alignment = List[tuple[int, int]]
Diff = List[tuple[range, range]]


def align_patience(seq_a:Sequence[_T], seq_b:Sequence[_T]) -> Alignment:
  '''
  Generate a sequence alignment using the Patience algorithm.
  '''
  alignment: Alignment = []
  _align(seq_a, seq_b, 0, 0, len(seq_a), len(seq_b), alignment)
  return alignment


def _align(seq_a:Sequence[_T], seq_b:Sequence[_T], pos_a:int, pos_b:int, end_a:int, end_b:int, alignment:List[tuple[int, int]]) -> None:
  '''
  Find alignment between `seq_a` and `seq_b`.
  Results accumulate in `alignment` as (idx_a, idx_b) pairs.
  '''
  #print(f'\n{pos_a} {pos_b}; {end_a} {end_b}')
  assert pos_a <= end_a and pos_b <= end_b, f'{pos_a} <= {end_a}, {pos_b} <= {end_b}'

  while pos_a < end_a and pos_b < end_b and seq_a[pos_a] == seq_b[pos_b]:
    alignment.append((pos_a, pos_b))
    pos_a += 1
    pos_b += 1

  if pos_a == end_a or pos_b == end_b: return
  end_alignment = []
  while pos_a < end_a and pos_b < end_b and seq_a[end_a-1] == seq_b[end_b-1]:
    end_alignment.append((end_a-1, end_b-1))
    end_a -= 1
    end_b -= 1

  if pos_a == end_a or pos_b == end_b: # TODO: optimize for len < 3 case?
    alignment.extend(reversed(end_alignment))
    return

  assert pos_a < end_a and pos_b < end_b, f'{pos_a} < {end_a}, {pos_b} < {end_b}'
  unique_alignment = unique_lcs(seq_a[pos_a:end_a], seq_b[pos_b:end_b])
  if unique_alignment:
    prev_a = pos_a
    prev_b = pos_b
    for a, b in unique_alignment:
      a += pos_a
      b += pos_b
      assert seq_a[a] == seq_b[b]
      _align(seq_a, seq_b, prev_a, prev_b, a, b, alignment)
      alignment.append((a, b))
      prev_a = a + 1
      prev_b = b + 1
    _align(seq_a, seq_b, prev_a, prev_b, end_a, end_b, alignment)
  alignment.extend(reversed(end_alignment))


def unique_lcs(seq_a:Sequence[_T], seq_b:Sequence[_T]) -> List[tuple[int, int]]:
  '''
  Find the longest common subset for unique elements.
  See http://en.wikipedia.org/wiki/Patience_sorting
  '''

  index_a = index_uniques(seq_a)
  index_b = index_uniques(seq_b)

  b_to_a:List[Optional[int]] = [None if index_b[el] is None else index_a.get(el) for el in seq_b]

  back_refs:List[Optional[int]] = [None] * len(seq_b)
  piles:List[int] = []
  lasts:List[int] = []
  pile_idx = 0
  for i_b, i_a in enumerate(b_to_a):
    if i_a is None: continue
    if piles and piles[-1] < i_a: # Optimization.
      pile_idx = len(piles)
    elif piles and piles[pile_idx] < i_a and (pile_idx == len(piles) - 1 or piles[pile_idx+1] > i_a): # Optimization.
      pile_idx += 1
    else:
      pile_idx = bisect(piles, i_a)
    if pile_idx: # Not the first pile; need a back_ref.
      back_refs[i_b] = lasts[pile_idx-1]
    if pile_idx < len(piles):
      piles[pile_idx] = i_a
      lasts[pile_idx] = i_b
    else:
      piles.append(i_a)
      lasts.append(i_b)

  if not piles: return []

  result:List[tuple[int, int]] = []
  last:Optional[int] = lasts[-1]
  while last is not None:
    o_a = b_to_a[last]
    assert o_a is not None
    result.append((o_a, last))
    last = back_refs[last]
  result.reverse()
  return result


def index_uniques(seq:Sequence[_T]) -> Dict[_T, Optional[int]]:
  index:Dict[_T, Optional[int]] = {}
  for i, el in enumerate(seq):
    index[el] = None if el in index else i
  return index
