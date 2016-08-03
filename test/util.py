#!/usr/bin/env python3

from utest import *
from pithy.util import *

momoize_tracker = []

@memoize()
def f(x, y):
  global memoize_tracker
  momoize_tracker.append((x, y))
  return x + y

f(0, 1)
f(0, 2)
f(0, 1)
f(0, 2)

utest_val([(0, 1), (0, 2)], momoize_tracker)
