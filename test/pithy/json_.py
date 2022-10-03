#!/usr/bin/env python3

from dataclasses import dataclass
from typing import NamedTuple

from pithy.json import parse_json, render_json
from pithy.untyped import Immutable
from utest import utest, utest_exc


class NT(NamedTuple):
  x: int

@dataclass
class DC:
  x: int

class Basic:
  def __init__(self, x: int):
    self.x = x


class SlotX:
  __slots__ = ['x']
  def __init__(self, x: int):
    self.x = x
  def __eq__(l, r: 'SlotX') -> bool:
    return l.x == r.x


class SlotXY(SlotX):
  __slots__ = ['y']
  def __init__(self, x: int, y: int):
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


# Render.

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


# Parse.
utest(Immutable(x=Immutable(y=0)), parse_json, '{"x": {"y":0}}', hook=Immutable)
utest(DC(x=1), parse_json, '{"x":1}', hooks=[DC])
utest(NT(x=1), parse_json, '{"x":1}', hooks=[NT])
utest(SlotX(x=1), parse_json, '{"x":1}', hooks=[SlotX])
utest(SlotXY(x=1, y=2), parse_json, '{"x":1, "y":2}', hooks=[SlotXY])

utest_exc(Exception, parse_json, '{"x":1}', hooks=[DC, NT])

utest_exc(TypeError("SlotXYZ.__init__() missing 1 required positional argument: 'z'"),
  parse_json, '{"x":1, "y":2}', hooks=[SlotXYZ]) # Not picked up because?

utest({'x': 1, 'y': 2, 'z': 3},
  parse_json, '{"x":1, "y":2, "z":3}', hooks=[SlotXYZ]) # not recognized because slots of SlotXYZ are only x,y.
