#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from utest import *
from pithy.lex import Lexer
from tolkien import Source, Token


# Token.diagnostic.

word_lexer = Lexer(invalid='inv', patterns=dict(
  word = r'\w+',
))

source = Source(name='test', text='1a b\n2c d')
tokens = list(word_lexer.lex(source, drop={'inv'})) # Note missing final newline.

utest('''\
test:1:1-3: word
| 1a b
  ~~
''', source.diagnostic, tokens[0], msg=tokens[0].kind)

utest('''\
test:1:4-5: word
| 1a b
     ~
''', source.diagnostic, tokens[1], msg=tokens[1].kind)

utest('''\
test:2:1-3: word
| 2c d\u23ce\u0353
  ~~
''', source.diagnostic, tokens[2], msg=tokens[2].kind)

utest('''\
test:2:4-5: word
| 2c d\u23ce\u0353
     ~
''', source.diagnostic, tokens[3], msg=tokens[3].kind)

# test the caret underline for zero-length matches and prefix.
utest('''\
PRE: test:1:1: MSG
| 1a b
  ^
''', source.diagnostic, tokens[0].pos_token(), prefix='PRE', msg='MSG')

