#!/usr/bin/env python3

from utest import utest, utest_exc
from pithy.seq import *


def list_seq_int_ranges(seq): return list(seq_int_ranges(seq))

utest([], list_seq_int_ranges, [])
utest([(0, 1), (2, 5)], list_seq_int_ranges, [0, (2,3), range(3, 5)])
