#!/usr/bin/env python3

from pithy.parse import Atom, Infix, Left, Parser, Precedence, Right, Struct, SuffixRule, token_extract_text
from pithy.py.lex import lexer
from tolkien import Source
from utest import *


arithmetic = Parser(lexer, dict(
    name=Atom('name', transform=token_extract_text),
    int=Atom('int_d', transform=lambda s, t: int(s[t])),
    paren=Struct('paren_o', 'expr', 'paren_c'),
    # TODO: unary plus, minus.
    expr=Precedence(
      ('int', 'name', 'paren'),
      Left(Infix('plus'), Infix('dash')),
      Left(Infix('star'), Infix('at'), Infix('slash'), Infix('slash2'), Infix('percent')),
      Right(Infix('star2')),
      Left(
        Infix('dot'),
        SuffixRule(Struct('brack_o', 'expr', 'brack_c'),
          transform=lambda s, t, l, r: ('[]', l, r)),
      ),
    )),
  literals=('brack_o', 'brack_c', 'paren_o', 'paren_c'),
  drop=('newline', 'spaces'))


utest(0, arithmetic.parse, 'expr', Source('', '0'))
utest('x', arithmetic.parse, 'expr', Source('', 'x'))

utest(('+',0,1), arithmetic.parse, 'expr', Source('', '0+1'))

utest(('+', ('+',0,1), 2), arithmetic.parse, 'expr', Source('', '0+1+2')) # Left associative.

utest(('+', 0, ('+',1,2)), arithmetic.parse, 'expr', Source('', '0+(1+2)')) # Parenthetical.

utest(('**', 2, ('**',1,2)), arithmetic.parse, 'expr', Source('', '2**1**2')) # Right associative.

utest(('+', ('+', 0, ('*',1,2)), 3), arithmetic.parse, 'expr', Source('', '0+1*2+3'))

utest(('+', ('*',0,1), ('*',2,3)), arithmetic.parse, 'expr', Source('', '0*1+2*3'))

utest(('[]', ('[]', 'a', 0), 1), arithmetic.parse, 'expr', Source('', 'a[0][1]'))
