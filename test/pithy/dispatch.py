#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from utest import utest
from pithy.dispatch import key_dispatched


class KeyDispatcher:

  @key_dispatched(lambda k: k)
  def echo(self, key:str) -> str:
    return key

  @key_dispatched(key='a') # type: ignore[no-redef]
  def echo(self, key:str) -> str:
    return 'A'

  @key_dispatched(key='b') # type: ignore[no-redef]
  def echo(self, key:str) -> str:
    return 'B'


d = KeyDispatcher()

utest('A', d.echo, 'a')
utest('B', d.echo, 'b')
utest('c', d.echo, 'c')
