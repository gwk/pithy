#!/usr/bin/env python3

from typing import Any

from utest import utest
from pithy.desc import outD
from pithy.io import outL


# Self-referencing list.
l_self:list[Any] = []
l_self.append(l_self)

# Cycle pair.
l_a:list[Any] = []
l_b = [l_a]
l_a.append(l_b)

objs = [
  # These should backref.
  l_self,
  l_a,
  l_b,
]

for obj in objs:
  outL()
  outD(repr(obj), obj)
