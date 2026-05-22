# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from operator import getitem
from typing import Iterable

from pithy.defaultlist import DefaultList
from utest import utest, utest_seq


ident = lambda idx: idx

utest_seq([0, 1], DefaultList, ident, fill_length=2)
utest_seq([-1, -1], DefaultList, ident, [-1, -1])
utest_seq([-1, -1], DefaultList, ident, [-1, -1], fill_length=2)
utest_seq([-1, -1, 2, 3], DefaultList, ident, [-1, -1], fill_length=4)


for i in range(3):
  utest(i, getitem, DefaultList(ident), i)


def set_idx_and_ret[T](l:list[T], idx:int, val:T) -> list[T]:
 l[idx] = val
 return l


def set_slc_and_ret[T](l:list[T], slc:slice, val:Iterable[T]) -> list[T]:
 l[slc] = val
 return l


utest_seq([-1], set_idx_and_ret, DefaultList(ident), 0, -1)
utest_seq([0, 1, -1], set_idx_and_ret, DefaultList(ident), 2, -1)

utest_seq([-1, -2], set_slc_and_ret, [], slice(0, 2), [-1, -2])
utest_seq([-1, -2], set_slc_and_ret, DefaultList(ident), slice(0, 2), [-1, -2])

utest_seq([-3, -4], set_slc_and_ret, [], slice(2, 4), [-3, -4]) # Builtin list behavior with out-of-bounds slices is weird.
utest_seq([0, 1, -3, -4], set_slc_and_ret, DefaultList(ident), slice(2, 4), [-3, -4])
