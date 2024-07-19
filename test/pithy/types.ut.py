# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter
from typing import Optional

from pithy.types import (is_a, req_bool, req_dict, req_float, req_int, req_list, req_opt_bool, req_opt_dict, req_opt_float,
  req_opt_int, req_opt_list, req_opt_str, req_str)
from utest import utest, utest_exc


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


utest(True, req_bool, True)
utest_exc(TypeError, req_bool, 0)

utest(0, req_int, 0)
utest_exc(TypeError, req_int, '')

utest(1.5, req_float, 1.5)
utest_exc(TypeError, req_float, 0)

utest('', req_str, '')
utest_exc(TypeError, req_str, 0)

utest([], req_list, [])
utest_exc(TypeError, req_list, '')

utest({}, req_dict, {})
utest_exc(TypeError, req_dict, '')

utest(None, req_opt_bool, None)
utest(True, req_opt_bool, True)
utest_exc(TypeError, req_opt_bool, '')

utest(None, req_opt_int, None)
utest(0, req_opt_int, 0)
utest_exc(TypeError, req_opt_int, '')

utest(None, req_opt_float, None)
utest(1.5, req_opt_float, 1.5)
utest_exc(TypeError, req_opt_float, '')

utest(None, req_opt_str, None)
utest('', req_opt_str, '')
utest_exc(TypeError, req_opt_str, 0)

utest(None, req_opt_list, None)
utest([], req_opt_list, [])
utest_exc(TypeError, req_opt_list, '')

utest(None, req_opt_dict, None)
utest({}, req_opt_dict, {})
utest_exc(TypeError, req_opt_dict, '')
