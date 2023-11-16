# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter
from typing import Optional

from pithy.types import is_a
from utest import utest


utest(True, is_a, None, type(None))
utest(False, is_a, None, int)

utest(True, is_a, 0, int)
utest(False, is_a, '', int)

utest(True, is_a, None, int|None)
utest(True, is_a, 0, int|None)
utest(False, is_a, '', int|None)

utest(True, is_a, [], list)
utest(True, is_a, {}, dict)
utest(True, is_a, (), tuple)
utest(True, is_a, set(), set)
utest(True, is_a, frozenset(), frozenset)

utest(True, is_a, [], list)
utest(True, is_a, {}, dict)
utest(True, is_a, (), tuple)
utest(True, is_a, set(), set)
utest(True, is_a, frozenset(), frozenset)

utest(True, is_a, [], list[int])
utest(True, is_a, [0], list[int])
utest(False, is_a, [0, None], list[int])

utest(True, is_a, [0, None], list[int|None])
utest(False, is_a, [0, None, ''], list[int|None])

utest(True, is_a, {}, dict[int,str])
utest(True, is_a, {0:'a'}, dict[int,str])
utest(False, is_a, {0:None}, dict[int,str])

utest(True, is_a, {None:None}, dict[int|None,str|None])
utest(False, is_a, {None:1}, dict[int|None,str|None])

utest(True, is_a, Counter(), Counter[int])
utest(True, is_a, Counter({1:1}), Counter[int])
utest(False, is_a, Counter({None:1}), Counter[int])

utest(True, is_a, Counter({None:1}), Counter[int|None])
utest(False, is_a, Counter({None:None}), Counter[int|None]) # Counters can be created with non-int values.

utest(True, is_a, None, Optional[None]) # Resolves to NoneType.
utest(True, is_a, None, int|None)
utest(False, is_a, 0, str|None)

utest(False, is_a, (), tuple[int,int])
utest(True, is_a, (0,0), tuple[int,int])
utest(True, is_a, (0,0), tuple[int,...])

utest(False, is_a, ('',0), tuple[int,int])
utest(False, is_a, ('',0), tuple[int,...])
