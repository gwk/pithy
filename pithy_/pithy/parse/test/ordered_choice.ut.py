# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.parse import Atom, choice_labeled, OneOrMore, OrderedChoice, parse_skel, Parser, Struct
from pithy.py.lex import lexer
from utest import utest


parser = Parser(lexer,
  drop=('spaces',),
  literals=('dot', 'paren_o', 'paren_c'),
  rules=dict(
    name=Atom('name'),
    dotted=OneOrMore('name', sep='dot'),
    call=Struct('name', 'paren_o', 'paren_c'),
    expr=OrderedChoice('call', 'dotted', transform=choice_labeled)))


def parse(s:str) -> Any: return parse_skel(parser, 'expr', s)

utest(('call', 'f'), parse, 'f()')
utest(('dotted', ['a']), parse, 'a')
utest(('dotted', ['a', 'b']), parse, 'a.b')
