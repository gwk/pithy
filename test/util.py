#!/usr/bin/env python3

from utest import *
from pithy.util import *


f_args = []

@memoize()
def f(x, y):
  global f_args
  f_args.append((x, y))
  return x + y

f(0, 1)
f(0, 2)
f(0, 1)
f(0, 2)

utest_val([(0, 1), (0, 2)], f_args, 'Memoize tracker check')
