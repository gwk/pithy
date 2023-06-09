#!/usr/bin/env python3

from typing import Counter, Dict, FrozenSet, List, Optional, Set, Tuple

from pithy.types import is_a
from utest import utest


utest(True, is_a, None, type(None))
utest(False, is_a, None, int)

utest(True, is_a, 0, int)
utest(False, is_a, '', int)

utest(True, is_a, None, Optional[int])
utest(True, is_a, 0, Optional[int])
utest(False, is_a, '', Optional[int])

utest(True, is_a, [], list)
utest(True, is_a, {}, dict)
utest(True, is_a, (), tuple)
utest(True, is_a, set(), set)
utest(True, is_a, frozenset(), frozenset)

utest(True, is_a, [], List)
utest(True, is_a, {}, Dict)
utest(True, is_a, (), Tuple)
utest(True, is_a, set(), Set)
utest(True, is_a, frozenset(), FrozenSet)

utest(True, is_a, [], List[int])
utest(True, is_a, [0], List[int])
utest(False, is_a, [0, None], List[int])

utest(True, is_a, [0, None], List[Optional[int]])
utest(False, is_a, [0, None, ''], List[Optional[int]])

utest(True, is_a, {}, Dict[int,str])
utest(True, is_a, {0:'a'}, Dict[int,str])
utest(False, is_a, {0:None}, Dict[int,str])

utest(True, is_a, {None:None}, Dict[Optional[int],Optional[str]])
utest(False, is_a, {None:1}, Dict[Optional[int],Optional[str]])

utest(True, is_a, Counter(), Counter[int])
utest(True, is_a, Counter({1:1}), Counter[int])
utest(False, is_a, Counter({None:1}), Counter[int])

utest(True, is_a, Counter({None:1}), Counter[Optional[int]])
utest(False, is_a, Counter({None:None}), Counter[Optional[int]]) # Counters can be created with non-int values.

utest(True, is_a, None, Optional[None]) # Resolves to NoneType.
utest(True, is_a, None, Optional[int])
utest(False, is_a, 0, Optional[str])

utest(False, is_a, (), Tuple[int,int])
utest(True, is_a, (0,0), Tuple[int,int])
utest(True, is_a, (0,0), Tuple[int,...])

utest(False, is_a, ('',0), Tuple[int,int])
utest(False, is_a, ('',0), Tuple[int,...])
