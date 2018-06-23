#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from utest import *
from pithy.dispatch import *


class C():

  @dispatched
  def describe(self, item:int) -> None: return f'int: {item}'

  @dispatched
  def describe(self, item:str) -> None: return f'str: {item}'

  @dispatched
  def measure(self, item:int) -> None: return item

  @dispatched
  def measure(self, item:str) -> None: return len(item)


c = C()
utest('int: 0', c.describe, 0)
utest('str: a', c.describe, 'a')
utest(0, c.measure, 0)
utest(3, c.measure, 'abc')
