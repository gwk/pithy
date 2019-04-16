#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from utest import *
from pithy.lex import Lexer
from pithy.token import *

# Token.diagnostic.

word_lexer = Lexer(invalid='inv', patterns=dict(
  word = r'\w+',
))

tokens = list(word_lexer.lex('1a b\n2c d', drop={'inv'})) # Note missing final newline.

utest('''\
PRE:1:1: word
| 1a b
  ~~''', tokens[0].diagnostic, prefix='PRE', msg=tokens[0].kind)

utest('''\
PRE:1:4: word
| 1a b
     ~''', tokens[1].diagnostic, prefix='PRE', msg=tokens[1].kind)

utest('''\
PRE:2:1: word
| 2c d
  ~~''', tokens[2].diagnostic, prefix='PRE', msg=tokens[2].kind)

utest('''\
PRE:2:4: word
| 2c d
     ~''', tokens[3].diagnostic, prefix='PRE', msg=tokens[3].kind)

# test the caret underline for zero-length matches.
utest('''\
PRE:1:1: MSG
| 1a b
  ^''', tokens[0].pos_token().diagnostic, prefix='PRE', msg='MSG')

