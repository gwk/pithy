#!/usr/bin/env python3

from utest import *
from pithy.meta import *



def disp_a(s:str) -> str: return 'A: ' + s

def disp_b(s:str) -> str: return 'B: ' + s


disp = dispatcher_for_names(prefix='disp_')

utest('A: x', disp, 'a', 'x')
utest('B: y', disp, 'b', 'y')

