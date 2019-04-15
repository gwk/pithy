#!/usr/bin/env python3

from dataclasses import dataclass

from pithy.desc import *
from pithy.io import outL
from utest import *


l_empty = [] # Noncyclical; referenced multiple times.

@dataclass
class DC:
  x:Any
  y:Any


objs = [
  0,
  '',
  'a',
  b'b',
  bytearray(),

  [],
  [0],
  [[0], [0]],
  [0, 1],
  [0, [1, 2]],
  [[0, 1], 2],
  [l_empty, l_empty, [l_empty]], # Should not backref.

  tuple(),
  (0,),
  (0, 0),
  (0, (1, 2)),

  {},
  {0:0, 1:1},
  {0:0, 1:{2:3, 4:5}},

  set(),
  {0},
  {0, 1},

  frozenset(),

  [DC(x=0, y=1), DC(x=[2,3], y=4)],
]

for obj in objs:
  outL()
  outD(repr(obj), obj)


outD('\nExact mode', {'a':[1, [2, 3]], 4:5}, exact=True)
