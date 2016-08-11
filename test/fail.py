#!/usr/bin/env python3

from utest import utest, utest_exc, utest_val


def raise_unexpected():
  raise Exception("unexpected")

utest(True, lambda *args, **kwargs: False, 0, 1, x='x', y='y')
utest(True, raise_unexpected)
utest_exc(Exception("expected"), lambda: True)
utest_exc(Exception("expected"), raise_unexpected)
utest_val(True, False, 'utest_val fail test')
