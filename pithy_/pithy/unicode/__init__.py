# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from itertools import chain
from typing import Iterable

from .data import blocks


# use pairs instead of real range objects because they are sortable, and faster to load in the interpreter.
CodeRange = tuple[int, int]
CodeRanges = tuple[CodeRange, ...]


# These (real) ranges are provided merely as a reference / convenience to the user.
ascii_range = range(0x80)
unicode_range = range(0x110000)

high_surrogates = (0xD800, 0xDC00)
low_surrogates  = (0xDC00, 0xE000)
surrogates = (high_surrogates[0], low_surrogates[1])


def codes_for_ranges(seq:Iterable[CodeRange]) -> Iterable[int]:
  return chain.from_iterable(range(*r) for r in seq)


def ranges_for_codes(seq:Iterable[int]) -> Iterable[CodeRange]:
  'codes must be sorted.'
  it = iter(seq)
  try: first = next(it)
  except StopIteration: return
  low = first
  end = first + 1
  for el in it:
    if el < end: raise ValueError(el)
    if el == end:
      end += 1
    else:
      yield (low, end)
      low = el
      end = el + 1
  yield (low, end)


def coalesce_sorted_ranges(seq:Iterable[CodeRange]) -> Iterable[CodeRange]:
  it = iter(seq)
  try: low, end = next(it)
  except StopIteration: return
  for r in it:
    l, e = r
    if e < l: raise ValueError(r) # bad range element.
    if l < low:
      raise ValueError(f'coalesce_sorted_ranges encountered unsorted range element: {r!r}; current coalesced range: {(low, end)}')
    if l <= end:
      end = max(end, e)
    else:
      yield (low, end)
      low = l
      end = e
  yield (low, end)


def union_sorted_ranges(*seqs:Iterable[CodeRange]) -> Iterable[CodeRange]:
  return coalesce_sorted_ranges(sorted(chain(*seqs)))


def intersect_sorted_ranges(seq_a:Iterable[CodeRange], seq_b:Iterable[CodeRange]) -> Iterable[CodeRange]:
  iter_a = iter(seq_a)
  iter_b = iter(seq_b)
  try: # iteration scope.
    a, ae = next(iter_a)
    b, be = next(iter_b)
    while True:
      while ae <= b: # drop a.
        a, ae = next(iter_a)
      if be <= a: # drop b.
        b, be = next(iter_b)
        continue # must continue from top, to retest a.
      s = max(a, b)
      if ae <= be:
        yield (s, ae)
        b, be = (ae, be) # if b is empty it will get dropped on next pass, assuming seq_a is coalesced.
      else:
        yield (s, be)
        a, ae = (be, ae) # if b is empty it will get dropped on next pass, assuming seq_b is coalesced.
  except StopIteration: return


def _mk_planes() -> tuple[CodeRanges, ...]:
  '''
  The ranges of each plane are the blocks of the current Unicode version, widened to multiples of 0x1000 and coalesced.
  The surrogates are excluded because those code points are not legally encodable.
  '''
  encodable = ((0, surrogates[0]), (surrogates[1], unicode_range.stop))
  plane_ranges:list[list[CodeRange]] = [[] for _ in range(17)]
  for low, end in sorted(blocks.values()):
    plane_ranges[low >> 16].append((low & ~0xFFF, (end + 0xFFF) & ~0xFFF))
  return tuple(tuple(intersect_sorted_ranges(coalesce_sorted_ranges(ranges), encodable)) for ranges in plane_ranges)


planes = _mk_planes()

abbreviated_planes:dict[str, CodeRanges] = {
  'BMP': planes[0], # Basic Multilingual Plane.
  'SMP': planes[1], # Supplementary Multilingual Plane.
  'SIP': planes[2], # Supplementary Ideographic Plane.
  'TIP': planes[3], # Tertiary Ideographic Plane.
  'SSP': planes[14], # Supplementary Special-purpose Plane.
  'SPUA_A': planes[15], # Supplementary Private Use Area A.
  'SPUA_B': planes[16], # Supplementary Private Use Area B.
}

all_plane_ranges = tuple(chain(*(planes)))
