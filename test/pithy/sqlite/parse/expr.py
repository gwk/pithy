#!/usr/bin/env python3

from typing import Any

from pithy.sqlite.parse import mk_sql_parser
from tolkien import Source
from utest import utest


simple_sql_parser = mk_sql_parser(simplify=True)


def parse_expr(s:str) -> Any:
  source = Source('<expr>', s)
  return simple_sql_parser.parse('expr', source)

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

utest(['a'], parse_expr, 'a')
utest(['"a"'], parse_expr, '"a"')


utest(('||', "'a'", "'b'"), parse_expr, "'a' || 'b'")

utest(('()', ['a'], ['b']), parse_expr, 'a(b)')
