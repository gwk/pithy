# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.parse import Atom, Choice, choice_syn, parse_skel, Parser, Struct, ZeroOrMore
from pithy.py.lex import lexer
from utest import utest


parser = Parser(lexer,
  drop=('spaces',),
  literals=('paren_o', 'paren_c'),
  rules=dict(
    name=Atom('name'),
    paren_expr=Struct('paren_o', ZeroOrMore('expr'), 'paren_c'),
    expr=Choice('name', 'paren_expr', transform=choice_syn)))

def parse(s:str) -> Any: return parse_skel(parser, 'expr', s)

utest('a', parse, 'a')
utest(['a', 'b'], parse, '(a b)')
utest(['a', ['b', 'c']], parse, '(a (b c))')
