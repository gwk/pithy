#!/usr/bin/env python3

from utest import *
from pithy.lex import *
from pithy.parse import *


lexer = Lexer(flags='x',
  patterns=dict(
    line    = r'\n',
    space   = r'\s+',
    name    = r'[a-z]+',
    int     = r'\d+',
    paren_o = r'\(',
    paren_c = r'\)',
    brckt_o = r'\[',
    brckt_c = r'\]',
    brace_o = r'\{',
    brace_c = r'\}',
    plus    = r'\+',
    minus   = r'-',
    star2   = r'\*\*',
    star    = r'\*',
    at      = r'@',
    slash2  = r'//',
    slash   = r'/',
    percent = r'%',
    dot     = r'\.',
    comma   = r',',
  ))


arithmetic = Parser(lexer, dict(
    name=Atom('name'),
    int=Atom('int', transform=lambda t: int(t.text)),
    paren=Prefix('paren_o', 'expr', 'paren_c'),
    # TODO: unary plus, minus.
    expr=Precedence(
      ('int', 'name', 'paren'),
      Left(Infix('plus'), Infix('minus')),
      Left(Infix('star'), Infix('at'), Infix('slash'), Infix('slash2'), Infix('percent')),
      Right(Infix('star2')),
      Left(
        Infix('dot'),
        SuffixRule(Prefix('brckt_o', 'expr', 'brckt_c'))
      ),
    )),
  drop=('space', 'line'))


utest(0, arithmetic.parse, 'expr', '0')
utest('x', arithmetic.parse, 'expr', 'x')

utest(('+',0,1), arithmetic.parse, 'expr', '0+1')

utest(('+', ('+',0,1), 2), arithmetic.parse, 'expr', '0+1+2') # Left associative.

utest(('+', 0, ('(', ('+',1,2))), arithmetic.parse, 'expr', '0+(1+2)') # Parenthetical.

utest(('**', 2, ('**',1,2)), arithmetic.parse, 'expr', '2**1**2') # Right associative.

utest(('+', ('+', 0, ('*',1,2)), 3), arithmetic.parse, 'expr', '0+1*2+3')

utest(('+', ('*',0,1), ('*',2,3)), arithmetic.parse, 'expr', '0*1+2*3')

utest(('', ('', 'a', ('[', 0)), ('[', 1)), arithmetic.parse, 'expr', 'a[0][1]')



chain_left = Parser(lexer, dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Left(Adjacency()),
      Left(Infix('plus')),
    )),
  drop=('space', 'line'))

utest(('', ('', 'a', 'b'), ('+', 'c', 'd')), chain_left.parse, 'expr', 'a b c+d')


def mk_comma_parser(sep_at_end:Optional[bool]) -> Parser:
  return Parser(lexer, dict(
      name=Atom('name'),
      seq=Quantity('name', sep='comma', sep_at_end=sep_at_end)),
    drop=('space', 'line'))

comma_opt = mk_comma_parser(sep_at_end=None)
comma_req = mk_comma_parser(sep_at_end=True)
comma_rej = mk_comma_parser(sep_at_end=False)

utest(('a', 'b', 'c'), comma_opt.parse, 'seq', 'a, b, c')
utest(('a', 'b', 'c'), comma_opt.parse, 'seq', 'a, b, c,')
utest(('a', 'b', 'c'), comma_req.parse, 'seq', 'a, b, c,')
utest(('a', 'b', 'c'), comma_rej.parse, 'seq', 'a, b, c')

