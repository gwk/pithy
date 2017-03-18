#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from utest import *
from enum import Enum
from pithy.lex import *


def test_lexer(lexer, string, **kwargs):
  for token, match in lexer.lex(string, **kwargs):
    yield token, match.group()


class Numbers(Lexer, Enum):
  Line = r'\n'
  Space = r' +'
  Num = r'\d+'

utest_seq([(Numbers.Num, '1'), (Numbers.Space, ' '), (Numbers.Num, '20'), (Numbers.Line, '\n')],
  test_lexer, Numbers, '1 20\n')

utest_seq([(Numbers.Num, '1'), (Numbers.Num, '20')],
  test_lexer, Numbers, '1 20\n', drop={Numbers.Line, Numbers.Space})

utest_seq_exc("LexError(<_sre.SRE_Match object; span=(2, 3), match='x'>,)", test_lexer, Numbers, '1 x 2')
utest_seq_exc("LexError(<_sre.SRE_Match object; span=(4, 5), match='x'>,)", test_lexer, Numbers, '1 2 x')


class Words(Lexer, Enum):
  Inv = None
  Word = r'\w+'

utest_seq([(Words.Inv, '!'), (Words.Word, 'a'), (Words.Inv, ' '), (Words.Word, 'b2'), (Words.Inv, '.')],
  test_lexer, Words, '!a b2.')

utest_seq([(Words.Word, 'a'), (Words.Word, 'b2')],
  test_lexer, Words, '!a b2.', drop={Words.Inv})


tokens = list(Words.lex('1a b\n2c d', drop={Words.Inv}))

utest('''\
TEST:1:1: Word
1a b
~~\
''', msg_for_match, tokens[0][1], prefix='TEST', msg=tokens[0][1].lastgroup)

utest('''\
TEST:1:4: Word
1a b
   ~\
''', msg_for_match, tokens[1][1], prefix='TEST', msg=tokens[1][1].lastgroup)

utest('''\
TEST:2:1: Word
2c d
~~\
''', msg_for_match, tokens[2][1], prefix='TEST', msg=tokens[2][1].lastgroup)

utest('''\
TEST:2:4: Word
2c d
   ~\
''', msg_for_match, tokens[3][1], prefix='TEST', msg=tokens[3][1].lastgroup)


class NoneErrorLexer(Lexer, Enum):
  Num = r'\d+'
  Inv = None
utest_exc(LexDefinitionError("member 1 'Inv' value is None (only member 0 may be signify the invalid token)"),
  NoneErrorLexer.lex, '')

class NonStringErrorLexer(Lexer, Enum):
  Num = 0
utest_exc(LexDefinitionError("member 0 'Num' value must be a string; found 0"),
  NonStringErrorLexer.lex, '')

class ParenErrorLexer(Lexer, Enum):
  Star = '*'
utest_exc(LexDefinitionError("member 0 'Star' pattern is invalid: *"),
  ParenErrorLexer.lex, '')

class GroupNameErrorLexer(Lexer, Enum):
  A = 'a'
  B = '(?P<A>a)'
utest_exc(LexDefinitionError("member 1 'B' pattern contains a conflicting capture group name: 'A'"),
  GroupNameErrorLexer.lex, '')



