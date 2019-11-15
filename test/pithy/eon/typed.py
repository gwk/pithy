#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import *

from pithy.eon import *
from utest import *


def parse(text:str, to:Type) -> Any:
  return parse_eon_or_fail(path='<test>', text=text, to=to)


utest(None, parse, '', to=None)

utest([1, 2], parse, '1\n2\n', to=List[int])

utest(dict(a=1, b=2), parse, '''
a: 1
b: 2
''',
  to=Dict[str,int])


utest(dict(a=(1, 2), b=(3, 4)), parse, '''
a:
  1
  2
b:
  3
  4
''',
  to=Dict[str,Tuple[int,int]])

utest(dict(a=[(1,2), (3,4)]), parse, '''
a:
  - 1
    2
  - 3
    4
''',
  to=Dict[str,List[Tuple[int,int]]])
