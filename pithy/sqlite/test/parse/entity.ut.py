# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.sqlite.parse import sql_parse_entity, sql_parse_schema_table
from utest import utest, utest_exc


utest('a', sql_parse_entity, 'a')
utest('a', sql_parse_entity, '"a"')

utest(('a', 'b'), sql_parse_schema_table, 'a.b')
utest(('a', 'b'), sql_parse_schema_table, '"a"."b"')


utest('a', sql_parse_entity, 'a')
utest('a', sql_parse_entity, '"a"')

utest_exc(ValueError("SQL entity is malformed: ''"), sql_parse_entity, '')

utest_exc(ValueError("SQL entity is malformed: 'a\"'"), sql_parse_entity, 'a"')

utest_exc(ValueError('SQL entity is malformed: "\'a\'"'), sql_parse_entity, "'a'")
