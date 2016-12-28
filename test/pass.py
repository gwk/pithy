#!/usr/bin/env python3

from utest import *


utest(True, lambda: True)
utest(True, lambda b: b, True)

def raise_expected(*args): raise Exception('expected')

utest_exc(Exception('expected'), raise_expected)

utest_seq([0, 1], range, 2)

def yield_then_raise(count):
  for i in range(count):
    yield i
  raise Exception('expected')

utest_seq_exc(Exception('expected'), yield_then_raise, 2)

utest_val(True, True, 'boolean test')
utest_val(1, 1, 'int test')
utest_val((0,1), (0,1), 'tuple test')

def add(a, b): return int(a) + int(b)
usymmetric(utest, 3, add, 1, 2)
usymmetric(utest_exc, ValueError("invalid literal for int() with base 10: 'a'"), add, 'a', 'a')

def a_plus_bc(a, b, c): return int(a) + int(b) * int(c)
usymmetric(utest, 7, a_plus_bc, 1, 2, 3)
usymmetric(utest_exc, ValueError("invalid literal for int() with base 10: 'a'"), a_plus_bc, 1, 'a', 'a')
