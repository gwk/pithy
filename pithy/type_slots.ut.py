# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.type_slots import all_slots
from utest import utest


class Basic:
  def __init__(self, x: int):
    self.x = x


class SlotX:
  __slots__ = ['x']
  def __init__(self, x: int):
    self.x = x


class SlotXSub(SlotX):
  'Subclass of slots class with no additional slots.'

class SlotXY(SlotXSub):

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
utest((), all_slots, Basic)
utest(('x',), all_slots, SlotX)
utest(('x',), all_slots, SlotXSub)
utest(('x', 'y'), all_slots, SlotXY)
utest(('x', 'y'), all_slots, SlotXYZ)
