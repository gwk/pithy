# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pyrrhus.byte_utils import find_byte, sum_bytes
from utest import utest, utest_exc


utest(0, sum_bytes, b'')
utest(294, sum_bytes, b'abc')

utest(2, find_byte, b'abc', 0x63)
utest(None, find_byte, b'abc', 0)
utest_exc(ValueError('byte must be in the range 0-255'), find_byte, b'abc', 256)
utest_exc(TypeError, find_byte, b'abc', byte=0x63) # `byte` is declared positional-only.
