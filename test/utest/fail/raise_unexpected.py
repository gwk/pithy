#!/usr/bin/env python3

from utest import utest, utest_exc, utest_seq, utest_seq_exc


'''
Test utest failure handling when an unexpected exception is raised.
'''


def raise_unexpected(): raise Exception('unexpected')

utest(True, raise_unexpected)

utest_exc(Exception('expected'), raise_unexpected)

utest_seq([0], raise_unexpected) # Raises in function; utest_seq cannot tell that the result is not a generator.


def yield_then_raise(count):
  for i in range(count):
    yield i
  raise Exception('unexpected')

utest_seq([0], yield_then_raise, 1)

utest_seq_exc(Exception('expected'), yield_then_raise, 1)
