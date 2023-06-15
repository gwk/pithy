from typing import Any

from pithy.sqlite.parse import sql_parser
from tolkien import Source
from utest import utest


def parse_expr(s:str) -> Any:
  source = Source('<expr>', s)
  return sql_parser.parse('expr', source)


parse_expr('a')
parse_expr("'a'")
parse_expr("'a'")
parse_expr('1')
parse_expr('+1')
parse_expr('-1')
parse_expr('1.0')
parse_expr('+1.0')
parse_expr('-1.0')
parse_expr('1.0e1')
parse_expr('1.0e-1')
parse_expr('1.0e+1')


print(parse_expr("'a' || 'b'"))
