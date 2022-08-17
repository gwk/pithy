#!/usr/bin/env python3

from utest import *
from pithy.sizediterable import *


utest_seq([(0, True)], iter_pairs_of_el_is_last, range(1))
utest_seq([(0, False), (1, True)], iter_pairs_of_el_is_last, range(2))
