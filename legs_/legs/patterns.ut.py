# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from legs.build import build_nfa
from legs.patterns import CharsetPattern, utf8_byte_range_seqs
from utest import utest, utest_seq


# A charset is emitted as a character class; each range excludes its end.
utest('[a-c]', CharsetPattern([(0x61, 0x64)]).gen_regex, flavor='py.re')
utest('[\\xe0-\\xe5]', CharsetPattern([(0xE0, 0xE6)]).gen_regex, flavor='py.re')
utest('a', CharsetPattern([(0x61, 0x62)]).gen_regex, flavor='py.re')


# Byte range sequences.

utest_seq([((0x70, 0x80),), ((0xC2, 0xE0), (0x80, 0xC0)), ((0xE0, 0xE1), (0xA0, 0xA4), (0x80, 0xC0))],
  utf8_byte_range_seqs, 0x70, 0x900)
utest_seq([], utf8_byte_range_seqs, 0xD800, 0xE000)
utest_seq([], utf8_byte_range_seqs, 5, 5)


# The UTF-8 NFA of a charset matches exactly the encodings of its code points.

def charset_nfa_matches(ranges:list[tuple[int,int]], codes:list[int]) -> list[bool]:
  nfa = build_nfa('main', [('k', CharsetPattern(ranges))], encoding='utf-8')
  return [bool(nfa.match(chr(code).encode())) for code in codes]

utest([False, True, True, True, True, True, True, True, False], charset_nfa_matches, [(0x7F, 0x10001)],
  [0x7E, 0x7F, 0x80, 0x7FF, 0x800, 0xD7FF, 0xE000, 0x10000, 0x10001])
utest([False, True, False, True, True, False], charset_nfa_matches, [(0x61, 0x62), (0x3040, 0x30A0)],
  [0x60, 0x61, 0x303F, 0x3040, 0x309F, 0x30A0])

def charset_nfa_matches_bytes(ranges:list[tuple[int,int]], texts:list[bytes]) -> list[bool]:
  nfa = build_nfa('main', [('k', CharsetPattern(ranges))], encoding='utf-8')
  return [bool(nfa.match(text)) for text in texts]

# Truncated, overlong and surrogate encodings do not match.
utest([False, False, False, False, True], charset_nfa_matches_bytes, [(0, 0x110000)],
  [b'\xe3\x81', b'\xc0\x80', b'\xed\xa0\x80', b'\xf4\x90\x80\x80', b'\xf4\x8f\xbf\xbf'])

