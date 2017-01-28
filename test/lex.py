#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from utest import *
from enum import Enum
from pithy.lex import *


class Tok(Lexer, Enum):
  Line = r'\n'
  Space = r' +'
  Num = r'\d+'
  Sym = r'(?!\d)\w+'


utest_seq([(Tok.Num, '1'), (Tok.Space, ' '), (Tok.Sym, 'a'), (Tok.Line, '\n')],
  Tok.lex, '1 a\n')


class ParenErrorLexer(Lexer, Enum):
  Paren = '('

utest_exc(LexUnescapedParenError('('), ParenErrorLexer.lex, '')

