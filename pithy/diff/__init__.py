# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from difflib import SequenceMatcher
from typing import Any, Callable, Dict, Sequence, TypeVar

from .patience import align_patience, Alignment, Diff


_T = TypeVar('_T')


def calc_diff(seq_a:Sequence[_T], seq_b:Sequence[_T], algorithm='patience', **kwargs:Any):
  alignment = alignment_fns[algorithm](seq_a, seq_b, **kwargs)
  improve_alignment(seq_a, seq_b, alignment)
  return diff_for_alignment(alignment, len(seq_a), len(seq_b))


def diff_for_alignment(alignment:Alignment, len_a:int, len_b:int) -> Diff:
  'Create a diff (list of range pairs) from an alignment (list of index pairs).'
  diff:Diff = []
  start_a = 0
  start_b = 0
  match_len = 0
  def flush(a:int, b:int) -> None:
    nonlocal start_a, start_b, match_len
    stop_a = start_a + match_len
    stop_b = start_b + match_len
    if match_len:
      diff.append((range(start_a, stop_a), range(start_b, stop_b)))
    if stop_a < a: diff.append((range(stop_a, a), range(stop_b, stop_b)))
    if stop_b < b: diff.append((range(a, a), range(stop_b, b)))
    start_a = a
    start_b = b

  for a, b in alignment:
    if start_a + match_len < a or start_b + match_len < b:
      flush(a, b)
      match_len = 1
    else:
      match_len += 1

  flush(len_a, len_b)
  return diff


def improve_alignment(seq_a:Sequence[_T], seq_b:Sequence[_T], alignment:Alignment) -> None:
  if not alignment: return
  prev_a, prev_b = alignment[0]
  for i, (a, b) in enumerate(alignment):
    last_a = a - 1
    last_b = b - 1
    if prev_a < last_a and prev_b  == last_b: # rem range.
      first_a = prev_a + 1 # index of first unaligned element.
      if seq_a[first_a] == seq_a[a]: # Change from bottom-aligned to top-aligned.
        a = first_a
        alignment[i] = (a, b)
    elif prev_a == last_a and prev_b < last_b: # add range.
      first_b = prev_b + 1
      if seq_b[first_b] == seq_b[b]:
        b = first_b
        alignment[i] = (a, b)
    prev_a = a
    prev_b = b


def validate_diff(seq_a:Sequence[_T], seq_b:Sequence[_T], diff:Diff, allow_empty=False) -> None:
  i_a = 0
  i_b = 0
  for r_a, r_b in diff:
    assert allow_empty or r_a or r_b
    if r_a:
      assert r_a.step == 1
      assert i_a == r_a.start
      i_a = r_a.stop
    if r_b:
      assert r_b.step == 1
      assert i_b == r_b.start
      i_b = r_b.stop
    if r_a and r_b:
      assert len(r_a) == len(r_b)
      for a, b in zip(r_a, r_b):
        assert seq_a[a] == seq_b[b]
  assert i_a == len(seq_a)
  assert i_b == len(seq_b)


def align_difflib(seq_a:Sequence[_T], seq_b:Sequence[_T], isjunk:Callable[[str], bool]=str.isspace, **kwargs) -> Alignment:
  'Diff using Python difflib.SequenceMatcher.'
  blocks:list[tuple[int, int, int]] = SequenceMatcher(isjunk=isjunk, a=seq_a, b=seq_b, **kwargs).get_matching_blocks() # type: ignore[arg-type, assignment]
  assert blocks[-1] == (len(seq_a), len(seq_b), 0)
  return [(i_a+j, i_b+j) for (i_a, i_b, l) in blocks for j in range(l)]


alignment_fns: Dict[str, Callable[..., Alignment]] = {
  'difflib': align_difflib,
  'patience': align_patience,
}
