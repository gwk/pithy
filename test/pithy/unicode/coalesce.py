#!/usr/bin/env python3

from pithy.unicode import *
from utest import utest_seq


utest_seq([], coalesce_sorted_ranges, [])
utest_seq([(0, 2), (3, 4)], coalesce_sorted_ranges, [(0, 1), (1, 2), (3, 4)])

utest_seq([], union_sorted_ranges, [], [])
utest_seq([(0, 2), (3, 8)], union_sorted_ranges, [(0, 1), (3, 7)], [(1, 2), (4, 5), (6, 8)])


def test_intersect(exp, a, b) -> None:
  utest_seq(exp, intersect_sorted_ranges, a, b)
  utest_seq(exp, intersect_sorted_ranges, b, a)

test_intersect([], [], [])
test_intersect([(0, 1), (2, 3)], [(0, 1), (2, 3)], [(0, 1), (2, 3)])
test_intersect([(0, 1)], [(0, 1), (2, 3)], [(0, 2), (3, 4)])
test_intersect([(1, 2)], [(0, 2)], [(1, 3)])
test_intersect([(0, 1), (2, 3)], [(0, 1), (2, 3)], [(0, 4)])
