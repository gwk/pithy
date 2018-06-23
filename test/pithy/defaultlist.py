#!/usr/bin/env python3

from utest import *
from pithy.defaultlist import *

utest_seq([0, 1], DefaultList, lambda i: i, fill_length=2)
utest_seq([-1, -1], DefaultList, lambda i: i, [-1, -1])

l = DefaultList(lambda i: i, fill_length=2)
