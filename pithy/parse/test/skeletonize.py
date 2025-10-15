# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.parse import Atom, Choice, choice_syn, Parser, Struct, ZeroOrMore
from pithy.py.lex import lexer
from tolkien import Source
from utest import utest


parser = Parser(lexer,
  drop=('spaces',),
  literals=('paren_o', 'paren_c'),
  rules=dict(
    name=Atom('name'),
    paren_expr=Struct('paren_o', ZeroOrMore('expr'), 'paren_c'),
    expr=Choice('name', 'paren_expr', transform=choice_syn)))


def parse_skel(s:str) -> Any:
  source = Source('expr', s)
  return parser.parse('expr', source, skeletonize=True)


utest('a', parse_skel, 'a')
utest(['a', 'b'], parse_skel, '(a b)')
utest(['a', ['b', 'c']], parse_skel, '(a (b c))')
