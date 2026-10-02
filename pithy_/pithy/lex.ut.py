# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Iterator

from pithy.lex import Lexer, LexMode, LexTrans, Source
from utest import utest, utest_exc, utest_seq, utest_seq_exc


# Lexer.

def run_lexer(lexer:Lexer, string:str, **kwargs:Any) -> Iterator[tuple[str,str]]:
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


# Ranges.

utest_seq([('num', '2'), ('spaces', ' '), ('num', '34')], run_lexer, num_lexer, '12 345', slc=slice(1, 5))
#^ Tokens do not extend past the end of the range.

utest_seq([('num', '45')], run_lexer, num_lexer, '12 345', slc=slice(-2, None))

utest_seq([('invalid', 'xy')], run_lexer, num_lexer, '1xyz2', slc=slice(1, 3))

utest_seq([], run_lexer, num_lexer, '12 345', slc=slice(4, 2))

utest_seq_exc(ValueError('slice step is not supported: slice(0, 4, 2)'), run_lexer, num_lexer, '12 345', slc=slice(0, 4, 2))

def lex_eot_pos(string:str, slc:slice|None) -> int:
  'Return the position of the `end_of_text` token.'
  return list(num_lexer.lex(Source(name='test', text=string), slc, eot=True))[-1].pos

utest(3, lex_eot_pos, '12 345', slice(0, 3))
utest(6, lex_eot_pos, '12 345', None)


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


# The source text must be a string.
utest_seq_exc(TypeError("pithy.lex.Lexer requires a source with `str` text; received bytes: Source('test', text=<bytes[1]>)"),
  num_lexer.lex, Source(name='test', text=b'1'))


# Start mode.
utest_seq([('chars', 'a b'), ('dq', '"'), ('chars', ' ')], run_lexer, str_lexer, 'a b" ', mode='string')
#^ The start mode is the root of the mode stack, so it is never popped.
utest_seq_exc(ValueError("unknown mode: 'nope'"), run_lexer, str_lexer, 'a', mode='nope')


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


def run_word_indent_lexer(string:str) -> Iterator[str]:
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
