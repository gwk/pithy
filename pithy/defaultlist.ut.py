# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from operator import getitem, setitem

from pithy.defaultlist import DefaultList
from utest import utest, utest_seq


utest_seq([0, 1], DefaultList, lambda i: i, fill_length=2)
utest_seq([-1, -1], DefaultList, lambda i: i, [-1, -1])

for i in range(3):
  utest(i, getitem, DefaultList(lambda i: i), i)

for i in range(3):
  l = DefaultList(lambda i: i)
  utest(None, setitem, l, i, 9)
  utest(9, getitem, l, i)
