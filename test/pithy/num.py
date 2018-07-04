#!/usr/bin/env python3

from utest import *
from pithy.num import *


utest_seq([0, 1, 2, 3], NumRange, 4)

utest_seq([0, 2, 4], NumRange, 0, 5, 2)

r = NumRange(0, 5, 2)
utest_val(4, r[-1])

utest_seq([0.0, 1.5, 3.0, 4.5], NumRange, 0, 6, 1.5)

utest_seq([0.0, 1.5, 3.0, 4.5, 6.0], NumRange, 0, 6, 1.5, closed=True)
