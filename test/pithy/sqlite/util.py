#!/usr/bin/env python3

from utest import utest, utest_exc
from pithy.sqlite.util import sql_unquote_entity

utest('', sql_unquote_entity, '')
utest('a', sql_unquote_entity, 'a')
utest('a', sql_unquote_entity, '"a"')

utest_exc(ValueError("SQL entity is malformed: 'a\"'"), sql_unquote_entity, 'a"')

utest_exc(ValueError('SQL entity is malformed (contains "\'"): "\'a\'"'), sql_unquote_entity, "'a'")