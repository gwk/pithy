#!/usr/bin/env python3

from utest import utest, utest_exc, utest_symmetric


def add(a, b): return int(a) + int(b)
utest_symmetric(utest, 0, add, 1, 2)
utest_symmetric(utest_exc, Exception('expected'), add, 'a', 'a')

def a_plus_bc(a, b, c): return int(a) + int(b) * int(c)
utest_symmetric(utest, 0, a_plus_bc, 1, 2, 3)
utest_symmetric(utest_exc, Exception('expected'), a_plus_bc, 1, 'a', 'a')
