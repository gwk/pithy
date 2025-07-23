# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from bisect import bisect
from itertools import chain

from . import abbreviated_planes, CodeRange, CodeRanges, intersect_sorted_ranges, union_sorted_ranges
from .categories import unicode_categories, unicode_category_aliases
from .data_11_00 import blocks, category_ranges


def is_code_in_charset(code:int, charset:CodeRanges) -> bool:
  p = (code, code)
  i = bisect(charset, p)
  if i < len(charset):
    s, e = charset[i]
    if s <= code < e: return True
  return i > 0 and code < charset[i - 1][1]


unicode_charsets:dict[str,CodeRanges] = {}
ascii_charsets:dict[str,CodeRanges] = {}

def _gen_charsets() -> None:

  # categories.
  for cat in unicode_categories:
    if cat.subcategories:
      unicode_charsets[cat.key] = tuple(sorted(chain(*(category_ranges[k] for k in cat.subcategories))))
    else:
      unicode_charsets[cat.key] = category_ranges[cat.key]
  # add aliases in a second pass to reuse range values by reference.
  for name, cat in unicode_category_aliases.items():
    if name in unicode_charsets: continue
    unicode_charsets[name] = unicode_charsets[cat.key]

  # blocks.
  for k, r in blocks.items():
    unicode_charsets[k] = (r,)

  # planes.
  for k, plane in abbreviated_planes.items():
    unicode_charsets[k] = plane

  def add(name:str, abbr:str, *ranges:CodeRange) -> None:
    unicode_charsets[name] = tuple(ranges)
    if abbr: unicode_charsets[abbr] = unicode_charsets[name]

  # Ascii.
  add('Ascii', 'A', (0x00, 0x80))
  Ascii = unicode_charsets['Ascii']

  for cat in unicode_categories:
    ranges = tuple(intersect_sorted_ranges(Ascii, unicode_charsets[cat.name]))
    if not ranges: continue
    k = 'Ascii_' + cat.name
    add(k, 'A' + cat.key, *ranges)
    ascii_charsets[k] = unicode_charsets[k]

  # Control characters. Note that 'Cc' also includes 0x7F (DEL).
  add('Control_0', 'C0', (0x0000, 0x0020))
  add('Control_1', 'C1', (0x0080, 0x00A0))

  # Common numeric sets for programming languages.
  add('Binary',       'Bin',  (0x30, 0x32))
  add('Quaternary',   'Quat', (0x30, 0x34))
  add('Octal',        'Oct',  (0x30, 0x38))
  add('Decimal',      'Dec',  (0x30, 0x3A)) # remove as redundant with Ascii_Number?
  add('Hexadecimal',  'Hex',  (0x30, 0x3A), (0x41, 0x47), (0x61, 0x67))

  # Miscellaneous.

  add('Visible', 'V', *union_sorted_ranges(*[unicode_charsets[k] for k in ['L', 'M', 'N', 'P', 'S']]))
  add('Readable', 'R', *union_sorted_ranges(*[unicode_charsets[k] for k in ['L', 'M', 'N', 'P', 'S', 'Z']]))

  add('Ascii_Visible', 'AV', *intersect_sorted_ranges(Ascii, unicode_charsets['V']))
  add('Ascii_Readable', 'AR', *intersect_sorted_ranges(Ascii, unicode_charsets['R']))

_gen_charsets()
