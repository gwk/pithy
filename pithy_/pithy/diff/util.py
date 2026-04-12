

from typing import Sequence, TypeVar


_T = TypeVar('_T')


def ranges_without_common_ends(seq_a:Sequence[_T], seq_b:Sequence[_T]) -> tuple[range, range]:
  pre_idx = 0
  for pre_idx, (el_a, el_b) in enumerate(zip(seq_a, seq_b)):
    if el_a != el_b: break
  post_a = len(seq_a)
  post_b = len(seq_b)
  for idx_a, idx_b in zip(reversed(range(pre_idx, len(seq_a))), reversed(range(pre_idx, len(seq_b)))):
    if seq_a[idx_a] != seq_b[idx_b]:
      post_a = idx_a + 1
      post_b = idx_b + 1
      break
  return (range(pre_idx, post_a), range(pre_idx, post_b))


def trim_common_ends(a:list[_T], b:list[_T]) -> tuple[list[_T], list[_T]]:
  r_a, r_b = ranges_without_common_ends(a, b)
  return a[r_a.start:r_a.stop], b[r_b.start:r_b.stop]


#def adjust_boundaries(seq:Sequence[_T],
