#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from utest import *
from pithy.dispatch import *


class C():

  @dispatched
  def describe(self, item:int) -> None: return f'int: {item}'

  @dispatched # type: ignore
  def describe(self, item:str) -> None: return f'str: {item}'

  @dispatched
  def measure(self, item:int) -> int: return item

  @dispatched # type: ignore
  def measure(self, item:str) -> int: return len(item)

c = C()
utest('int: 0', c.describe, 0)
utest('str: a', c.describe, 'a')
utest(0, c.measure, 0)
utest(3, c.measure, 'abc')



class KeyDispatcher:

  @key_dispatched(lambda k: k)
  def echo(self, key:str) -> str:
    return key

  @key_dispatched(key='a')
  def echo(self, key:str) -> str:
    return 'A'

  @key_dispatched(key='b')
  def echo(self, key:str) -> str:
    return 'B'


d = KeyDispatcher()

utest('A', d.echo, 'a')
utest('B', d.echo, 'b')
utest('c', d.echo, 'c')
