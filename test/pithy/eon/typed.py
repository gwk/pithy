#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Type

from pithy.eon import parse_eon_or_fail
from utest import utest


def parse(text:str, to:Type) -> Any:
  return parse_eon_or_fail(path='<test>', text=text, to=to)


utest(None, parse, '', to=None)

utest([1, 2], parse, '1\n2\n', to=list[int])

utest(dict(a=1, b=2), parse, '''
a: 1
b: 2
''',
  to=dict[str,int])


utest(dict(a=(1, 2), b=(3, 4)), parse, '''
a:
  1
  2
b:
  3
  4
''',
  to=dict[str,tuple[int,int]])

utest(dict(a=[(1,2), (3,4)]), parse, '''
a:
  - 1
    2
  - 3
    4
''',
  to=dict[str,list[tuple[int,int]]])
