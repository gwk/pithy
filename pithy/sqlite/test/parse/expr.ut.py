# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.parse import syn_skeleton
from pithy.sqlite.parse import mk_sql_parser
from tolkien import Source
from utest import utest


simple_sql_parser = mk_sql_parser()


def parse_expr(s:str) -> Any:
  source = Source('<expr>', s)
  return syn_skeleton(simple_sql_parser.parse('expr', source), source=source)

# Strings.
utest("''" , parse_expr, "''")
utest("'a'", parse_expr, "'a'")

# Numbers.
utest('1', parse_expr, '1')
utest('+1', parse_expr, '+1')
utest('-1', parse_expr, '-1')
utest('1.0', parse_expr, '1.0')
utest('+1.0', parse_expr, '+1.0')
utest('-1.0', parse_expr, '-1.0')
utest('1.0e1', parse_expr, '1.0e1')
utest('1.0e-1', parse_expr, '1.0e-1')
utest('1.0e+1', parse_expr, '1.0e+1')

utest('a', parse_expr, 'a')
utest(('a', 'b'), parse_expr, 'a.b')

utest('"a"', parse_expr, '"a"')


utest(('||', "'a'", "'b'"), parse_expr, "'a' || 'b'")

utest(('a', ['b']), parse_expr, 'a(b)')
utest(('a', ['b', 'c']), parse_expr, 'a(b, c)')

# Function calls.
utest(('LOWER', ['a']), parse_expr, 'LOWER(a)')
utest(('LOWER', ['a', 'b']), parse_expr, 'LOWER(a, b)')

# 'GLOB', 'IF', 'LIKE', 'REPLACE' are keywords and function names.
utest(('GLOB', ['a']), parse_expr, 'GLOB(a)')
utest(('IF', ['a', 'b', 'c']), parse_expr, 'IF(a, b, c)')
utest(('LIKE', ['a', 'b']), parse_expr, 'LIKE(a, b)')
utest(('REPLACE', ['a', 'b', 'c']), parse_expr, 'REPLACE(a, b, c)')

# Dotted names.
utest(('a', 'b'), parse_expr, 'a.b')
utest(('a', 'b', 'c'), parse_expr, 'a.b.c')
