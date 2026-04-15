# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from typing import Any

from pithy.json import parse_json, render_json, req_json_dict, req_json_list, req_opt_json_dict, req_opt_json_list
from utest import utest, utest_exc


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
  def __eq__(l, r:Any) -> bool:
    return isinstance(r, SlotX) and l.x == r.x


class SlotXY(SlotX):
  __slots__ = ['y']
  def __init__(self, x: int, y: int):
    super().__init__(x=x)
    self.y = y
  def __eq__(l, r:Any) -> bool:
    return super().__eq__(r) and l.y == r.y


class SlotXYZ(SlotXY):
  'Subclass of slots classes that uses a backing `__dict__` for attribute `z`.'
  def __init__(self, x: int, y: int, z: int):
    super().__init__(x=x, y=y)
    self.z = z
  def __eq__(l, r:Any) -> bool:
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

utest_exc(TypeError , render_json, ...) # Ellipsis type does not encode by default.


# Parse.
utest(None, parse_json, None)
utest({'x': {'x': 0}}, parse_json, '{"x": {"x":0}}')
utest(DC(x=0), parse_json, '{"x":0}', object_hook=lambda d: DC(**d))


# req_ functions.

utest({}, req_json_dict, {})
utest_exc(TypeError, req_json_dict, [])

utest([], req_json_list, [])
utest_exc(TypeError, req_json_list, {})

utest(None, req_opt_json_dict, None)
utest({}, req_opt_json_dict, {})
utest_exc(TypeError, req_opt_json_dict, [])

utest(None, req_opt_json_list, None)
utest([], req_opt_json_list, [])
utest_exc(TypeError, req_opt_json_list, {})
