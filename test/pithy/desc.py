#!/usr/bin/env python3

from utest import *
from pithy.desc import *
from pithy.io import outL

l_empty = [] # Noncyclical; referenced multiple times.

objs = [
  0,
  '',
  'a',
  b'b',
  bytearray(),

  [],
  [0],
  [0, 1],
  [0, [1, 2]],
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
]

for obj in objs:
  outL()
  outD(repr(obj), obj)
