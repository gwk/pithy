#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from utest import *
from pithy.dispatch import *


class C():

  class describe(MethodDispatch): pass

  @describe
  def _(self, item:int) -> None: return f'int: {item}'

  @describe
  def _(self, item:str) -> None: return f'str: {item}'

  describe = describe.method()


  class measure(MethodDispatch): pass

  @measure
  def _(self, item:int) -> None: return item

  @measure
  def _(self, item:str) -> None: return len(item)

  measure = measure.method()


c = C()
utest('int: 0', c.describe, 0)
utest('str: a', c.describe, 'a')
utest(0, c.measure, 0)
utest(3, c.measure, 'abc')
