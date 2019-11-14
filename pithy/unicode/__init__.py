# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from itertools import chain
from typing import Dict, Iterable, Tuple


# use pairs instead of real range objects because they are sortable, and faster to load in the interpreter.
CodeRange = Tuple[int, int]
CodeRanges = Tuple[CodeRange, ...]


# These (real) ranges are provided merely as a reference / convenience to the user.
ascii_range = range(0x80)
unicode_range = range(0x110000)

high_surrogates = (0xD800, 0xDC00)
low_surrogates  = (0xDC00, 0xE000)
surrogates = (high_surrogates[0], low_surrogates[1])


planes:Tuple[CodeRanges, ...] = (
  ( # 0: Basic Multilingual Plane.
    # Note: the surrogates range is excluded because those code points are not legally encodable.
    (0x0000, surrogates[0]),
    (surrogates[1], 0x10000),
  ),
  ( # 1: Supplementary Multilingual Plane.
    (0x10000, 0x15000),
    (0x16000, 0x19000),
    (0x1B000, 0x1C000),
    (0x1D000, 0x20000),
  ),
  ( # 2: Supplementary Ideographic Plane.
    (0x20000, 0x2D000),
    (0x2F000, 0x30000),
  ),
  (), # 3: Unassigned.
  (), # 4: Unassigned.
  (), # 5: Unassigned.
  (), # 6: Unassigned.
  (), # 7: Unassigned.
  (), # 8: Unassigned.
  (), # 9: Unassigned.
  (), # 10: Unassigned.
  (), # 11: Unassigned.
  (), # 12: Unassigned.
  (), # 13: Unassigned.
  ( # 14: Supplement­ary Special-purpose Plane.
    (0xE0000, 0xE1000),
  ),
  ( # 15: Supplement­ary Private Use Area Plane A (SPUA-A).
    (0xF0000, 0x100000),
  ),
  ( # 16: Supplement­ary Private Use Area Plane A (SPUA-B).
    (0x100000, 0x110000),
  ),
)

abbreviated_planes:Dict[str, CodeRanges]  = {
  'BMP': planes[0],
  'SMP': planes[1],
  'SIP': planes[2],
  'SSP': planes[14],
  'SPUA_A': planes[15],
  'SPUA_B': planes[16],
}

all_plane_ranges = tuple(chain(*(planes)))


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

