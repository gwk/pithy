# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.parse import Atom, choice_labeled, OneOrMore, OrderedChoice, Parser, Quantity, Struct, syn_skeleton, ZeroOrMore
from pithy.py.lex import lexer
from tolkien import Source
from utest import utest


parser = Parser(lexer,
  drop=('spaces',),
  literals=('dot', 'paren_o', 'paren_c'),
  rules=dict(
    name=Atom('name'),
    dotted=OneOrMore('name', sep='dot'),
    call=Struct('name', 'paren_o', 'paren_c'),
    expr=OrderedChoice('call', 'dotted', transform=choice_labeled)))


def parse_skel(s:str, rule:str='expr') -> Any:
  source = Source('expr', s)
  #return parser.parse('expr', source)
  return syn_skeleton(parser.parse(rule, source), source=source)


utest(('call', 'f'), parse_skel, 'f()')
utest(('dotted', ['a']), parse_skel, 'a')
utest(('dotted', ['a', 'b']), parse_skel, 'a.b')
