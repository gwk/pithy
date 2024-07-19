# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.dispatch import key_dispatched_method
from utest import utest


class KeyDispatcher:

  @key_dispatched_method(lambda k: k)
  def echo(self, key:str) -> str:
    return key

  @echo.register(key='a')
  def _(self, key:str) -> str:
    return 'A'

  @echo.register(key='b')
  def _(self, key:str) -> str:
    return 'B'


d = KeyDispatcher()

utest('A', d.echo, 'a')
utest('B', d.echo, 'b')
utest('c', d.echo, 'c')
