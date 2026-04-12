# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.range import NumRange
from utest import utest_seq, utest_val


utest_seq([0, 1, 2, 3], NumRange, 4)

utest_seq([0, 2, 4], NumRange, 0, 5, 2)

r = NumRange(0, 5, 2)
utest_val(4, r[-1])

utest_seq([0.0, 1.5, 3.0, 4.5], NumRange, 0, 6, 1.5)

utest_seq([0.0, 1.5, 3.0, 4.5, 6.0], NumRange, 0, 6, 1.5, closed=True)

utest_seq([0.0, 0.5], NumRange, 0, 1, 0.5)
utest_seq([0.0, 0.5, 1.0], NumRange, 0, 1, 0.5, closed=True)
utest_seq([0.0, 0.5, 1.0], NumRange, 0, 1.1, 0.5)
utest_seq([0.0, 0.5, 1.0], NumRange, 0, 1.1, 0.5, closed=True)

utest_seq([0, 1/3, 2/3], NumRange, 0, 1, 1/3)
utest_seq([0, 1/3, 2/3, 1], NumRange, 0, 1, 1/3, closed=True)
