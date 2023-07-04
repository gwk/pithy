#!/usr/bin/env python3

from pithy.meta import dispatcher_for_defs
from utest import utest


def disp_a(s:str) -> str: return 'A: ' + s

def disp_b(s:str) -> str: return 'B: ' + s


disp = dispatcher_for_defs(prefix='disp_')

utest('A: x', disp, 'a', 'x')
utest('B: y', disp, 'b', 'y')
