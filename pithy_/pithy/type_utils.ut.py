# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter
from typing import Annotated, Literal, Optional, Union

from pithy.type_utils import (is_a, normalize_type_form, req_bool, req_dict, req_float, req_int, req_list, req_opt_bool,
  req_opt_dict, req_opt_float, req_opt_int, req_opt_list, req_opt_str, req_str, req_type)
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


type Direction = Literal['n', 's', 'e', 'w']

utest(True, is_a, 'n', Direction)
utest(False, is_a, 'x', Direction)
utest(True, is_a, 'n', Literal['n', 's'])
utest(False, is_a, 'x', Literal['n', 's'])

utest(True, is_a, 1, Literal[1, 2])
utest(False, is_a, True, Literal[1, 2]) # Per PEP 586, True is not a member of Literal[1].
utest(True, is_a, True, Literal[True])
utest(False, is_a, 1, Literal[True])
utest(True, is_a, None, Literal['n', None]) # None is permitted in Literal.

utest(True, is_a, ['n', 's'], list[Literal['n', 's']]) # Literal nested in a generic.
utest(False, is_a, ['n', 'x'], list[Literal['n', 's']])
utest(True, is_a, 'n', Union[int, Literal['n']]) # Literal nested in a union.
utest(True, is_a, 'n', (int, Direction)) # Alias in a tuple of types.


utest(True, is_a, None, None) # None is shorthand for NoneType.
utest(False, is_a, 0, None)

utest(True, is_a, 0, Annotated[int, 'meta']) # Annotated delegates to the underlying type.
utest(False, is_a, '', Annotated[int, 'meta'])
utest(True, is_a, [0], list[Annotated[int, 'meta']]) # Annotated nested in a generic.


type AliasedAnnotatedDirection = Annotated[Direction, 'meta']

utest(int, normalize_type_form, int)
utest(type(None), normalize_type_form, None)
utest(int, normalize_type_form, Annotated[int, 'meta'])
utest(Literal['n', 's', 'e', 'w'], normalize_type_form, Direction)
utest(Literal['n', 's', 'e', 'w'], normalize_type_form, AliasedAnnotatedDirection) # Alias of Annotated of alias.


utest(0, req_type, 0, int)
utest_exc(TypeError, req_type, '', int)

utest([0], req_type, [0], list[int])
utest_exc(TypeError, req_type, [''], list[int])

utest('n', req_type, 'n', Direction)
utest_exc(TypeError, req_type, 'x', Direction)

utest(None, req_type, None, None)
utest_exc(TypeError, req_type, 0, None)


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
