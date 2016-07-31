#!/usr/bin/env python3

from utest import utest, utest_exc

utest(True, lambda: True)


def raise_expected():
  raise Exception("expected")

utest_exc(Exception("expected"), raise_expected)
