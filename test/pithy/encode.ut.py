# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from types import EllipsisType
from typing import Any

from pithy.encode import all_slots, encode_obj
from utest import utest, utest_call, utest_exc


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


class SlotXY(SlotX):
  __slots__ = ['y']
  def __init__(self, x: int, y: int):
    super().__init__(x=x)
    self.y = y


class SlotXYZ(SlotXY):
  'Subclass of slots classes that uses a backing `__dict__` for attribute `z`.'
  def __init__(self, x: int, y: int, z: int):
    super().__init__(x=x, y=y)
    self.z = z


# all_slots.
utest(frozenset(), all_slots, Basic)
utest(frozenset({'x'}), all_slots, SlotX)
utest(frozenset({'x', 'y'}), all_slots, SlotXY)
utest(frozenset({'x', 'y'}), all_slots, SlotXYZ)


# encode_obj.

# Specializations.
utest(None, encode_obj, None)
utest(False, encode_obj, False)
utest(1, encode_obj, 1)
utest('a', encode_obj, 'a')
utest('type', encode_obj, type)


utest_exc(TypeError('cannot encode object of type ellipsis'), encode_obj, ...) # Ellipsis is not registered by default.

@encode_obj.register
def _(obj:EllipsisType) -> Any: return str(obj)

utest('Ellipsis', encode_obj, ...) # Now the Ellipsis type is registered.


utest([None], encode_obj, [None])

utest([0], encode_obj, range(1))
utest({'x':1}, encode_obj, DC(x=1)) # dataclass.
utest({'x':1}, encode_obj, Basic(x=1)) # __dict__ only.

# __slots__ classes.
utest({'x':1}, encode_obj, SlotX(x=1))
utest({'x':1,'y':2}, encode_obj, SlotXY(x=1, y=2))
utest({'x':1,'y':2,'z':3}, encode_obj, SlotXYZ(x=1, y=2, z=3))
