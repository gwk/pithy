#!/usr/bin/env python3

from utest import utest, utest_exc, utest_seq, utest_seq_exc, utest_symmetric, utest_val


utest(True, lambda *args, **kwargs: False, 0, 1, x='x', y='y')

utest_exc(Exception('expected'), lambda: True)

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
