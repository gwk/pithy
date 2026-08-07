# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pyrrhus import add, hello, hello_from_bin, scale
from utest import utest, utest_exc


utest('Hello from pyrrhus!', hello_from_bin)
utest('Hello from pyrrhus!', hello)

utest(5, add, 2, 3)
utest(-1, add, 2, -3)
utest(0, add, 0, 0)

utest_exc(OverflowError, add, 1 << 63, 0) # The declared type is `int`, which maps to i64, so out-of-range arguments raise.
utest_exc(OverflowError('integer addition overflowed'), add, (1 << 63) - 1, 1) # Raised by the implementation.

utest([], scale, [])
utest([1.0, 2.0], scale, [1.0, 2.0]) # `factor` defaults to 1.0.
utest([3.0, 6.0], scale, [1.0, 2.0], factor=3.0)
utest_exc(TypeError, scale, [1.0], 3.0) # `factor` is declared keyword-only.
