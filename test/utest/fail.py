#!/usr/bin/env python3

from utest import utest, utest_exc, utest_seq, utest_seq_exc, utest_val, utest_symmetric


def raise_unexpected(): raise Exception('unexpected')

utest(True, lambda *args, **kwargs: False, 0, 1, x='x', y='y')
utest(True, raise_unexpected)

utest_exc(Exception('expected'), lambda: True)
utest_exc(Exception('expected'), raise_unexpected)

utest_seq([0], raise_unexpected) # raises in function.
utest_seq([0], range, 0) # unexpected sequence.
utest_seq([0], lambda: 0) # returns non-iterable.

utest_seq_exc(Exception('expected'), range, 1) # does not raise expected.
utest_seq_exc(Exception('expected'), lambda: 0) # returns non-iterable.

def yield_then_raise(count):
  for i in range(count):
    yield i
  raise Exception('unexpected')

utest_seq_exc(Exception('expected'), yield_then_raise, 1) # returns non-iterable.


utest_val(True, False, 'utest_val fail test')

def add(a, b): return int(a) + int(b)
utest_symmetric(utest, 0, add, 1, 2)
utest_symmetric(utest_exc, Exception('expected'), add, 'a', 'a')

def a_plus_bc(a, b, c): return int(a) + int(b) * int(c)
utest_symmetric(utest, 0, a_plus_bc, 1, 2, 3)
utest_symmetric(utest_exc, Exception('expected'), a_plus_bc, 1, 'a', 'a')
