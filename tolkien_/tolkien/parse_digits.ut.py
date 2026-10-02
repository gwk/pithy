# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from tolkien import Source, Token
from utest import utest


def parse_digits(text:str|bytes, offset:int, base:int) -> int:
  source:Source = Source(name='test', text=text)
  return source.parse_digits(Token(0, len(text)), offset=offset, base=base)


utest(10, parse_digits, '10', 0, 10)
utest(2, parse_digits, '0b10', 2, 2)
utest(4, parse_digits, '0q10', 2, 4)
utest(8, parse_digits, '0o10', 2, 8)
utest(10, parse_digits, '0d10', 2, 10)
utest(16, parse_digits, b'0x10', 2, 16)
utest(0xffff_ffff_ffff_ffff, parse_digits, '0x__ffff_ffff_ffff_ffff', 2, 16) # Non-digit characters are ignored.
utest(0x1_0000_0000_0000_0000, parse_digits, '0x1_0000_0000_0000_0000', 2, 16) # Python integers do not overflow.
