#!/usr/bin/env python3

from dataclasses import dataclass
from typing import *

from pithy.json import *
from utest import *


class NT(NamedTuple):
  x: int

@dataclass
class DC:
  x: int

class Basic:
  def __init__(self, x: int) -> None:
    self.x = x


class SlotX:
  __slots__ = ['x']
  def __init__(self, x: int) -> None:
    self.x = x
  def __eq__(l, r: 'SlotX') -> bool:
    return l.x == r.x


class SlotXY(SlotX):
  __slots__ = ['y']
  def __init__(self, x: int, y: int) -> None:
    super().__init__(x=x)
    self.y = y
  def __eq__(l, r: 'SlotXY') -> bool:
    return super().__eq__(r) and l.y == r.y


class SlotXYZ(SlotXY):
  'Subclass of slots classes that uses a backing `__dict__` for attribute `z`.'
  def __init__(self, x: int, y: int, z: int):
    super().__init__(x=x, y=y)
    self.z = z
  def __eq__(l, r: 'SlotXYZ') -> bool:
    return super().__eq__(r) and l.z == r.z


utest('null', render_json, None)
utest('1', render_json, 1)
utest('"a"', render_json, 'a')
utest('[\n  null\n]', render_json, [None])

utest('[\n  0\n]', render_json, range(1))
utest('{"x":1}', render_json, DC(x=1), indent=None) # dataclass.
utest('{"x":1}', render_json, Basic(x=1), indent=None) # __dict__ only.

# __slots__ classes.
utest('{"x":1}', render_json, SlotX(x=1), indent=None)
utest('{"x":1,"y":2}', render_json, SlotXY(x=1, y=2), indent=None)
utest('{"x":1,"y":2,"z":3}', render_json, SlotXYZ(x=1, y=2, z=3), indent=None)

utest('"Ellipsis"', render_json, ...) # `str` fallback.

utest(DC(x=1), parse_json, '{"x":1}', types=[DC])
utest(NT(x=1), parse_json, '{"x":1}', types=[NT])
utest(SlotX(x=1), parse_json, '{"x":1}', types=[SlotX])
utest(SlotXY(x=1, y=2), parse_json, '{"x":1, "y":2}', types=[SlotXY])

utest_exc(Exception, parse_json, '{"x":1}', types=[DC, NT])

utest_exc(TypeError("__init__() missing 1 required positional argument: 'z'"),
  parse_json, '{"x":1, "y":2}', types=[SlotXYZ]) # Not picked up because?

utest({'x': 1, 'y': 2, 'z': 3},
  parse_json, '{"x":1, "y":2, "z":3}', types=[SlotXYZ]) # not recognized because slots of SlotXYZ are only x,y.
