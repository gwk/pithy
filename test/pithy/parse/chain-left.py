#!/usr/bin/env python3

from pithy.parse import Adjacency, Atom, Infix, Left, Parser, Precedence
from pithy.py.lex import lexer
from tolkien import Source
from utest import *


chain_left = Parser(lexer, dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Left(Adjacency()),
      Left(Infix('plus')),
    )),
  drop=('spaces',))

utest((('a', 'b'), ('+', 'c', 'd')), chain_left.parse, 'expr', Source('', 'a b c+d'))
utest(((('+', 'a', 'b'), 'c'), 'd'), chain_left.parse, 'expr', Source('', 'a+b c d'))

