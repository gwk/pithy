# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from legs.patterns import CharsetPattern, utf8_byte_range_seqs
from utest import utest, utest_seq


def bytes_regex_matches(ranges:list[tuple[int,int]], char:str) -> bool:
  'Test whether the bytes regex generated for the charset matches the UTF-8 encoding of `char`.'
  regex = CharsetPattern(ranges).gen_regex(flavor='py.re.bytes')
  return bool(re.fullmatch(regex.encode(), char.encode()))


# An ASCII charset is emitted as a character class.
utest('[a-c]', CharsetPattern([(0x61, 0x64)]).gen_regex, flavor='py.re.bytes')

# A non-ASCII charset matches every code point of each range, and not the exclusive end.
latin_range = [(0xE0, 0xE6)] # U+E0 through U+E5.
for code in range(0xE0, 0xE6): utest(True, bytes_regex_matches, latin_range, chr(code))
utest(False, bytes_regex_matches, latin_range, chr(0xDF))
utest(False, bytes_regex_matches, latin_range, chr(0xE6))

# Surrogates cannot be encoded and are omitted.
utest(True, bytes_regex_matches, [(0xD7FF, 0xE001)], chr(0xD7FF))
utest(True, bytes_regex_matches, [(0xD7FF, 0xE001)], chr(0xE000))


# Byte range sequences.

utest_seq([((0x70, 0x80),), ((0xC2, 0xE0), (0x80, 0xC0)), ((0xE0, 0xE1), (0xA0, 0xA4), (0x80, 0xC0))],
  utf8_byte_range_seqs, 0x70, 0x900)
utest_seq([], utf8_byte_range_seqs, 0xD800, 0xE000)
utest_seq([], utf8_byte_range_seqs, 5, 5)


def mismatched_codes(ranges:list[tuple[int,int]]) -> list[int]:
  'Return the code points near the range and encoding boundaries for which the bytes regex disagrees with the ranges.'
  regex = re.compile(CharsetPattern(ranges).gen_regex(flavor='py.re.bytes').encode())
  boundaries = {0, 0x80, 0x800, 0xD800, 0xE000, 0x10000, 0x110000, *(code for r in ranges for code in r)}
  codes = sorted({code for b in boundaries for code in range(b - 3, b + 3) if 0 <= code < 0x110000})
  codes.extend(range(0, 0x110000, 251)) # A sparse sample of the whole code space.
  return [code for code in codes if not (0xD800 <= code < 0xE000)
    and bool(regex.fullmatch(chr(code).encode())) != any(start <= code < end for start, end in ranges)]


for ranges in [
  [(0x70, 0x900)],
  [(0x7F0, 0x10100)],
  [(0xD000, 0xE100)],
  [(0, 0x110000)],
  [(0x80, 0x81), (0x7FF, 0x801), (0xFFFF, 0x10001), (0x10FFFF, 0x110000)],
  [(0x123, 0x4567), (0x89AB, 0xCDEF), (0x1F300, 0x2A6DF)],
]:
  utest([], mismatched_codes, ranges)
