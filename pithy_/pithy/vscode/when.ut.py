# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.logic import And, Eq, Ne, Or
from pithy.parse import Source, syn_skeleton
from pithy.vscode.when import when_parser
from utest import utest


def parse_expr(s:str) -> Any:
  source = Source('<expr>', s)
  return syn_skeleton(when_parser.parse('expr', source), source=source)


utest('""' , parse_expr, '""')
utest('a', parse_expr, 'a')

utest(Or(l='a', r=And(l='b', r='c')), parse_expr, 'a || b && c')

utest(Or(l=And(l='a', r='b'), r='c'), parse_expr, 'a && b || c')
utest(And(l=Or(l='a', r='b'), r='c'), parse_expr, '(a || b) && c')
utest(And(l='a', r=Or(l='b', r='c')), parse_expr, 'a && (b || c)')

utest(Eq(l='a', r='b'), parse_expr, 'a == b')
utest(Ne(l='a', r='b'), parse_expr, 'a != b')
