#!/usr/bin/env python3

from utest import utest_seq, utest_val, utest
from pithy.util import lazy_property, memoize, nt_items
from dataclasses import dataclass
from typing import NamedTuple


# lazy_property.

class C:

  @lazy_property
  def p(self) -> object: return object()


c = C()
o1 = c.p
utest_val(o1, c.p, 'subsequent call to lazy property returns same value.')
o2 = object()
c.p = o2
utest_val(o2, c.p, 'lazy property can be set to new value.')

# memoize.

f_args:list[tuple[int,int]] = []
@memoize()
def f1(x:int, y:int) -> int:
  global f_args
  f_args.append((x, y))
  return x + y

f1(0, 1)
f1(0, 2)
f1(0, 1)
f1(0, 2)

utest_val([(0, 1), (0, 2)], f_args, desc='@memoize call history')

@memoize # test that memoize decorator also works without parens.
def f2(x): return x

utest(0, f2, 0)


# nt_items.

class NT(NamedTuple):
  x: int

utest_seq([('x', 1)], nt_items, NT(x=1))
