#!/usr/bin/env python3

from utest import *


def raise_unexpected(): raise Exception('unexpected')

utest(True, lambda *args, **kwargs: False, 0, 1, x='x', y='y')
utest(True, raise_unexpected)

utest_exc(Exception('expected'), lambda: True)
utest_exc(Exception('expected'), raise_unexpected)

utest_seq([0], range, 0)
utest_seq([0], lambda: 0)

utest_val(True, False, 'utest_val fail test')

def add(a, b): return int(a) + int(b)
usymmetric(utest, 0, add, 1, 2)
usymmetric(utest_exc, Exception('expected'), add, 'a', 'a')

def a_plus_bc(a, b, c): return int(a) + int(b) * int(c)
usymmetric(utest, 0, a_plus_bc, 1, 2, 3)
usymmetric(utest_exc, Exception('expected'), a_plus_bc, 1, 'a', 'a')
