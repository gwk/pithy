#!/usr/bin/env python3

from utest import utest, utest_exc, utest_val

utest(True, lambda: True)


def raise_expected():
  raise Exception("expected")

utest_exc(Exception("expected"), raise_expected)


utest_val(True, True, 'boolean test')
utest_val(1,1, 'int test')
utest_val((0,1),(0,1), 'tuple test')
