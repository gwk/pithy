# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from legs.patterns import CharsetPattern
from utest import utest


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
