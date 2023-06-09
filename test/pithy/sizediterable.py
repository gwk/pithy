#!/usr/bin/env python3

from pithy.sizediterable import iter_pairs_of_el_is_last
from utest import utest_seq


utest_seq([(0, True)], iter_pairs_of_el_is_last, range(1))
utest_seq([(0, False), (1, True)], iter_pairs_of_el_is_last, range(2))
