#!/usr/bin/env python3

from utest import *
from pithy.buffer import *


utest_seq([], Buffer, [])
utest_seq([0, 1, 2], Buffer, range(3))


b = Buffer(range(4))

utest_val(True, b.is_live)
utest(0, next, b)

b.push(-1)
utest(-1, b.peek)
b.push(-2)
utest(-2, b.peek)
utest(-2, next, b)
utest_val(True, b.is_live)
utest(-1, next, b)

utest_val(True, b.is_live)
utest(1, b.peek)
utest(1, next, b)

utest([2, 3], list, b)
utest_val(False, b.is_live)
utest(None, b.peek, default=None)
utest_exc(StopIteration(), next, b)

b = Buffer(range(5))
utest_seq([0, 1], b.take_while, pred=lambda el: el < 2)
utest_seq([2],    b.peek_while, pred=lambda el: el < 3)
utest_seq([2, 3], b.peek_while, pred=lambda el: el < 4)
utest_seq([2, 3, 4], b.peek_while, pred=lambda el: True)
b.drop_while(pred=lambda el: el < 3)
utest_seq([3, 4], b.peek_while, pred=lambda el: True)
utest_seq([3, 4], b.take_while, pred=lambda el: True)
utest_seq([], b.take_while, pred=lambda el: True)

b = Buffer('abc')
utest(['a', 'b'], b.peeks, 2)
utest(['a', 'b'], b.take, 2)

utest_exc(StopIteration(), Buffer('ab').take, 3)
utest_exc(StopIteration(), Buffer('ab').peeks, 3)
utest(['a', 'b'], Buffer('ab').take, 3, short=True)
utest(['a', 'b'], Buffer('ab').peeks, 3, short=True)
utest(['a', 'b', None], Buffer('ab').take, 3, default=None)
utest(['a', 'b', None], Buffer('ab').peeks, 3, default=None)

