#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from utest import *
from pithy.lex import *


# Lexer.

def run_lexer(lexer, string, **kwargs):
  'Run `lexer` on `string`, yielding (kind, text) pairs.'
  for match in lexer.lex(string, **kwargs):
    yield match.lastgroup, match[0]


num_lexer = Lexer(patterns=dict(
  line  = r'\n',
  space = r' +',
  num   = r'\d+',
))

utest_seq([('num', '1'), ('space', ' '), ('num', '20'), ('line', '\n')],
  run_lexer, num_lexer, '1 20\n')

utest_seq([('num', '1'), ('num', '20')],
  run_lexer, num_lexer, '1 20\n', drop={'line', 'space'})

utest_seq_exc("LexError(<re.Match object; span=(2, 3), match='x'>)", run_lexer, num_lexer, '1 x 2')
utest_seq_exc("LexError(<re.Match object; span=(4, 5), match='x'>)", run_lexer, num_lexer, '1 2 x')


word_lexer = Lexer(invalid='inv', patterns=dict(
  word = r'\w+',
))

utest_seq([('inv', '!'), ('word', 'a'), ('inv', ' '), ('word', 'b2'), ('inv', '.')],
  run_lexer, word_lexer, '!a b2.')

utest_seq([('word', 'a'), ('word', 'b2')],
  run_lexer, word_lexer, '!a b2.', drop={'inv'})


utest_exc(Lexer.DefinitionError("member 0 'num' value must be a string; found 0"),
  Lexer, patterns=dict(num=0))

utest_exc(Lexer.DefinitionError("member 0 'star' pattern is invalid: (?P<star>*)"),
  Lexer, patterns=dict(star='*'))

utest_exc(Lexer.DefinitionError("member 1 'b' pattern contains a conflicting capture group name: 'a'"),
  Lexer, patterns=dict(a='a', b='(?P<a>b)'))

utest_exc(Lexer.DefinitionError('Lexer instance must define at least one pattern'), Lexer)

utest_seq_exc(Lexer.DefinitionError(
  "Zero-length patterns are disallowed, because they cause the following character to be skipped.\n"
  "  kind: caret; match: <re.Match object; span=(0, 0), match=''>"),
  Lexer(patterns=dict(caret='^', a='a')).lex, 'a')


# match_diagnostic.

tokens = list(word_lexer.lex('1a b\n2c d', drop={'inv'})) # note missing final newline.

utest('''\
PRE:1:1: word
| 1a b
  ~~\
''', match_diagnostic, tokens[0], prefix='PRE', msg=tokens[0].lastgroup)

utest('''\
PRE:1:4: word
| 1a b
     ~\
''', match_diagnostic, tokens[1], prefix='PRE', msg=tokens[1].lastgroup)

utest('''\
PRE:2:1: word
| 2c d
  ~~\
''', match_diagnostic, tokens[2], prefix='PRE', msg=tokens[2].lastgroup)

utest('''\
PRE:2:4: word
| 2c d
     ~\
''', match_diagnostic, tokens[3], prefix='PRE', msg=tokens[3].lastgroup)

# test the caret underline for zero-length matches.
utest('''\
PRE:1:1: MSG
| abc
  ^\
''', match_diagnostic, re.match('^', 'abc'), prefix='PRE', msg='MSG')

