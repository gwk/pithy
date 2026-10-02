# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from itertools import chain, pairwise
from unicodedata import category, east_asian_width, unidata_version

from pithy.unicode import coalesce_sorted_ranges, CodeRange, ranges_for_codes
from pithy.unicode.data import blocks, category_ranges, double_width_codes, unicode_version
from utest import utest, utest_seq, utest_val


code_space = (0, 0x110000)


# The category ranges partition the code space: they cover it and their sizes sum to its size.
all_category_ranges = sorted(chain(*category_ranges.values()))
utest_seq([code_space], coalesce_sorted_ranges, all_category_ranges)
utest_val(code_space[1], sum(end - low for low, end in all_category_ranges), 'total size of category ranges')

for cat, ranges in category_ranges.items():
  utest_val(tuple(coalesce_sorted_ranges(ranges)), ranges, f'coalesced ranges of category {cat}')


def is_ordered_and_disjoint(ranges:list[CodeRange]) -> bool:
  return all(low < end for low, end in ranges) and all(a[1] <= b[0] for a, b in pairwise(ranges))

utest(True, is_ordered_and_disjoint, list(blocks.values()))
utest(True, is_ordered_and_disjoint, double_width_codes)
utest_val([], [name for name, (low, end) in blocks.items() if low % 16 or end % 16], 'blocks not aligned to 16')


def stdlib_category_ranges() -> dict[str,tuple[CodeRange,...]]:
  codes:dict[str,list[int]] = {}
  for code in range(*code_space):
    codes.setdefault(category(chr(code)), []).append(code)
  return { cat : tuple(ranges_for_codes(cat_codes)) for cat, cat_codes in codes.items() }

def stdlib_double_width_codes() -> list[CodeRange]:
  return list(ranges_for_codes(code for code in range(*code_space) if east_asian_width(chr(code)) in 'FW'))

# The standard library data is only comparable when it has the same Unicode version.
if unidata_version == unicode_version:
  utest(category_ranges, stdlib_category_ranges)
  utest(double_width_codes, stdlib_double_width_codes)
