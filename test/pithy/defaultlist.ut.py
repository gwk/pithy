# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.defaultlist import DefaultList
from utest import utest_seq


utest_seq([0, 1], DefaultList, lambda i: i, fill_length=2)
utest_seq([-1, -1], DefaultList, lambda i: i, [-1, -1])

l = DefaultList(lambda i: i, fill_length=2)
