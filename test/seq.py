#!/usr/bin/env python3

from utest import *
from pithy.seq import *


utest_seq([], seq_int_ranges, [])
utest_seq([(0, 1), (2, 5)], seq_int_ranges, [0, (2,3), range(3, 5)])
