#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from utest import utest_seq, utest_exc, utest_seq_exc
from pithy.lex import *
from typing import Any


# Lexer.

def run_lexer(lexer, string:str, **kwargs:Any) -> None:
  'Run `lexer` on `string`, yielding (kind, text) pairs.'
  source = Source(name='test', text=string)
  for token in lexer.lex(source, **kwargs):
    yield token.kind, source[token]


num_lexer = Lexer(patterns=dict(
  newline  = r'\n',
  spaces = r' +',
  num   = r'\d+',
))

utest_seq([('num', '1'), ('spaces', ' '), ('num', '20'), ('newline', '\n')],
  run_lexer, num_lexer, '1 20\n')

utest_seq([('num', '1'), ('num', '20')],
  run_lexer, num_lexer, '1 20\n', drop={'newline', 'spaces'})

utest_seq([('num','0'), ('newline','\n'), ('end_of_text','')],
  run_lexer, num_lexer, '0\n', eot=True)

utest_seq([('num', '1'), ('invalid', 'x'), ('num', '2')], run_lexer, num_lexer, '1 x 2', drop='spaces')


word_lexer = Lexer(patterns=dict(
  word = r'\w+',
))

utest_seq([('invalid', '!'), ('word', 'a'), ('invalid', ' '), ('word', 'b2'), ('invalid', '.')],
  run_lexer, word_lexer, '!a b2.')

utest_seq([('word', 'a'), ('word', 'b2')],
  run_lexer, word_lexer, '!a b2.', drop={'invalid'})


utest_exc(Lexer.DefinitionError("'num' pattern value must be a string; found 0"),
  Lexer, patterns=dict(num=0))

utest_exc(Lexer.DefinitionError("'star' pattern is invalid: (?P<star>*)"),
  Lexer, patterns=dict(star='*'))

utest_exc(Lexer.DefinitionError("'b' pattern contains a conflicting capture group name: 'a'"),
  Lexer, patterns=dict(a='a', b='(?P<a>b)'))

utest_exc(Lexer.DefinitionError('Lexer instance must define at least one pattern'), Lexer, patterns={})

utest_seq_exc(
  Lexer.DefinitionError("Zero-length patterns are disallowed.\n  kind: caret; match: <re.Match object; span=(0, 0), match=''>"),
  Lexer(patterns=dict(caret='^', a='a')).lex, Source(name='test', text='a'))


# Modes.

str_lexer = Lexer(patterns=dict(
  newline  = r'\n',
  spaces = r' +',
  dq    = r'"',
  chars = r'[^"\\]+',
  esc = r'\\"|\\\\'),
  modes=[
    LexMode('main', ['newline', 'spaces', 'dq']),
    LexMode('string', ['chars', 'esc', 'dq']),
  ],
  transitions=[
    LexTrans('main', kind='dq', mode='string', pop='dq', consume=True)])


utest_seq([
  ('dq', '"'), ('chars', 'a'), ('dq', '"'), ('spaces', ' '),
  ('dq', '"'), ('chars', 'b'), ('esc', '\\"'), ('esc', '\\\\'), ('dq', '"'), ('newline', '\n')],
  run_lexer, str_lexer, '"a" "b\\"\\\\"\n')


word_indent_lexer = Lexer(patterns=dict(
  newline  = r'\n',
  spaces = r' +',
  word    = r'\w+',
  comment = '#[^\n]+'),
  modes=[LexMode('main', ['newline', 'spaces', 'word'], indents=True)])


word_indent_text = '''
a
  b

  c
    d
'''


def run_word_indent_lexer(string:str) -> None:
  'Run `lexer` on `string`, yielding token text strings.'
  source = Source(name='test', text=string)
  for token in word_indent_lexer.lex(source, drop={'spaces', 'comment'}):
    yield source[token] if token.kind == 'word' else token.kind

utest_seq([
  'newline', 'a',
  'newline', 'indent', 'b',
  'newline',
  'newline', 'c',
  'newline', 'indent', 'd',
  'newline', 'dedent', 'dedent'],
  run_word_indent_lexer, word_indent_text)
