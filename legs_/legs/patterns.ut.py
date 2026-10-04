# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

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
