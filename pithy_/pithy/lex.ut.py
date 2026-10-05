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

utest_seq([('num', '1'), ('invalid', 'xy')], run_lexer, num_lexer, '1xy')
#^ An invalid token extends to the next match or to the end of the range.

utest_seq([], run_lexer, num_lexer, '')
utest_seq([('end_of_text', '')], run_lexer, num_lexer, '', eot=True)


# Pattern order. The first pattern that matches at a position wins, not the longest.

utest_seq([('a', 'a'), ('invalid', 'b')], run_lexer, Lexer(patterns=dict(a='a', ab='ab')), 'ab')
utest_seq([('ab', 'ab'), ('a', 'a')], run_lexer, Lexer(patterns=dict(ab='ab', a='a')), 'aba')

# A capture group within a pattern does not change the kind.
utest_seq([('pair', 'ab')], run_lexer, Lexer(patterns=dict(pair='(?P<left>a)(?P<right>b)')), 'ab')


# Flags.

utest_seq([('word', 'aB')], run_lexer, Lexer(flags='i', patterns=dict(word='[a-z]+')), 'aB')
utest_seq([('word', 'ab')], run_lexer, Lexer(flags='x', patterns=dict(word='a b')), 'ab')


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

utest_exc(Lexer.DefinitionError('invalid global regex flag: z'), Lexer, flags='z', patterns=dict(a='a'))

utest_exc(Lexer.DefinitionError(
  "'c' pattern is invalid: (?x)(?P<c>#)\n  note: global flags: 'x'\n  note: unescaped verbose mode comments break lexer"),
  Lexer, flags='x', patterns=dict(c='#'))

utest_exc(Lexer.DefinitionError("'invalid' pattern name collides with the invalid token name"), Lexer, patterns=dict(invalid='a'))
utest_exc(Lexer.DefinitionError("name is reserved: 'end_of_text'"), Lexer, patterns=dict(end_of_text='a'))
utest_exc(Lexer.DefinitionError("invalid name: '1a'"), Lexer, patterns={'1a': 'a'})

utest_seq_exc(
  Lexer.DefinitionError("Zero-length patterns are disallowed.\n  kind: caret; match: <re.Match object; span=(0, 0), match=''>"),
  Lexer(patterns=dict(caret='^', a='a')).lex, Source(name='test', text='a'))


# Modes.

ab_patterns = dict(a='a', b='b')

utest('main', lambda: Lexer(patterns=ab_patterns).main)
utest(frozenset({'a', 'b'}), lambda: Lexer(patterns=ab_patterns).modes['main'].kind_set)
#^ Without modes, a `main` mode holds every pattern.

utest('first', lambda: Lexer(patterns=ab_patterns, modes=[LexMode('first', 'a'), LexMode('second', 'b')]).main)
#^ The first mode is the default start mode. A single kind can be given as a string.

# A mode kind that is not a plain name is a regular expression that selects pattern names.
utest(frozenset({'str_d', 'str_s', 'a'}),
  lambda: Lexer(patterns=dict(str_s="'", str_d='"', a='a', b='b'), modes=[LexMode('main', ['str_.*', 'a'])]).modes['main'].kind_set)

# The modes can be any iterable, including a generator.
utest(frozenset({'newline', 'spaces', 'indent', 'dedent'}),
  lambda: Lexer(patterns=dict(newline='\n', spaces=' +'),
    modes=(mode for mode in [LexMode('main', ['newline', 'spaces'], indents=True)])).kinds)

utest_exc(Lexer.DefinitionError("mode 'main' includes nonexistent pattern: 'c'"),
  Lexer, patterns=ab_patterns, modes=[LexMode('main', ['a', 'c'])])

utest_exc(Lexer.DefinitionError("duplicate mode name: 'main'"),
  Lexer, patterns=ab_patterns, modes=[LexMode('main', ['a']), LexMode('main', ['b'])])

utest_exc(Lexer.DefinitionError("mode name conflicts with pattern name: 'a'"), Lexer, patterns=ab_patterns, modes=[LexMode('a', ['a'])])

utest_exc(Lexer.DefinitionError("expected LexMode; received: 'main'"), Lexer, patterns=ab_patterns, modes=['main'])

utest_exc(Lexer.DefinitionError("mode 'main' wildcard pattern regex does not match any patterns: c.*"),
  Lexer, patterns=ab_patterns, modes=[LexMode('main', ['c.*'])])

utest_exc(Lexer.DefinitionError("mode 'main' includes invalid pattern regex: (a"),
  Lexer, patterns=ab_patterns, modes=[LexMode('main', ['(a'])])

utest_exc(Lexer.DefinitionError("mode 'main' has no patterns"), Lexer, patterns=ab_patterns, modes=[LexMode('main', [])])


# Transitions.

def run_modes(lexer:Lexer, string:str, **kwargs:Any) -> Iterator[str]:
  'Run `lexer` on `string`, yielding a `mode:text` string for each token.'
  source = Source(name='test', text=string)
  for token in lexer.lex(source, **kwargs):
    yield f'{token.mode}:{source[token]}'


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

# The pushing token has the parent mode. The popping token has the child mode.
utest_seq(['main:"', 'string:a', 'string:"', 'main: '], run_modes, str_lexer, '"a" ')

# A consuming pop does not let the parent push again on the same token.
utest_seq(['main:"', 'string:"', 'main:"', 'string:"'], run_modes, str_lexer, '""""')

# Dropped tokens still cause transitions.
utest_seq([('chars', 'a'), ('spaces', ' ')], run_lexer, str_lexer, '"a" ', drop={'dq'})

# The `end_of_text` token has the mode that is current at the end, so an unclosed frame is visible.
utest_seq(['main:"', 'string:a', 'string:'], run_modes, str_lexer, '"a', eot=True)
utest_seq(['main:"', 'string:a', 'string:"', 'main:'], run_modes, str_lexer, '"a"', eot=True)


# The source text must be a string.
utest_seq_exc(TypeError("pithy.lex.Lexer requires a source with `str` text; received bytes: Source('test', text=<bytes[1]>)"),
  num_lexer.lex, Source(name='test', text=b'1'))


# Start mode.
utest_seq([('chars', 'a b'), ('dq', '"'), ('chars', ' ')], run_lexer, str_lexer, 'a b" ', mode='string')
#^ The start mode is the root of the mode stack, so it is never popped.
utest_seq_exc(ValueError("unknown mode: 'nope'"), run_lexer, str_lexer, 'a', mode='nope')


# A transition can have several parent modes, which allows nesting.

group_lexer = Lexer(patterns=dict(paren_o=r'\(', paren_c=r'\)', word=r'\w+'),
  modes=[
    LexMode('main', ['paren_o', 'paren_c', 'word']),
    LexMode('group', ['paren_o', 'paren_c', 'word'])],
  transitions=[
    LexTrans(('main', 'group'), kind='paren_o', mode='group', pop='paren_c', consume=True)])

utest_seq(['main:(', 'group:a', 'group:(', 'group:b', 'group:)', 'group:c', 'group:)', 'main:d'], run_modes, group_lexer, '(a(b)c)d')

# A closing kind in the root frame is an ordinary token.
utest_seq(['main:)', 'main:a'], run_modes, group_lexer, ')a')


# A transition can have several opening kinds and several closing kinds.

note_lexer = Lexer(patterns=dict(hash='#', slashes='//', newline=r'\n', semi=';', text=r'[^#/;\n]+'),
  modes=[
    LexMode('main', ['hash', 'slashes', 'newline', 'semi', 'text']),
    LexMode('note', ['newline', 'semi', 'text'])],
  transitions=[
    LexTrans('main', kind=('hash', 'slashes'), mode='note', pop=('newline', 'semi'), consume=True)])

utest_seq(['main:a', 'main:#', 'note:b', 'note:;', 'main:c', 'main://', 'note:d', 'note:\n', 'main:e'],
  run_modes, note_lexer, 'a#b;c//d\ne')


# A pop that does not consume lets the parent frame act on the closing token.
# Here each section header closes the current section, and then `main` opens the next one.

section_lexer = Lexer(patterns=dict(head_a='A:', head_b='B:', x='x', y='y'),
  modes=[
    LexMode('main', ['head_a', 'head_b']),
    LexMode('a', ['head_a', 'head_b', 'x']),
    LexMode('b', ['head_a', 'head_b', 'y'])],
  transitions=[
    LexTrans('main', kind='head_a', mode='a', pop=('head_a', 'head_b'), consume=False),
    LexTrans('main', kind='head_b', mode='b', pop=('head_a', 'head_b'), consume=False)])

utest_seq([('head_a', 'A:'), ('x', 'x'), ('head_b', 'B:'), ('y', 'y'), ('invalid', 'x'), ('head_a', 'A:'), ('x', 'x')],
  run_lexer, section_lexer, 'A:xB:yxA:x')

utest_seq(['main:A:', 'a:x', 'a:B:', 'b:y', 'b:A:', 'a:A:', 'a:x'], run_modes, section_lexer, 'A:xB:yA:A:x')
#^ The header that closes a section has the mode of that section.


# A pop that does not consume cascades to the parent frame, which can pop in turn.

def cascade_lexer(*, consume:bool) -> Lexer:
  return Lexer(patterns=dict(angle='<', brack=r'\[', semi=';', word=r'\w+'),
    modes=[LexMode('main', '.*'), LexMode('outer', '.*'), LexMode('inner', '.*')],
    transitions=[
      LexTrans('main', kind='angle', mode='outer', pop='semi', consume=True),
      LexTrans('outer', kind='brack', mode='inner', pop='semi', consume=consume)])

utest_seq(['main:<', 'outer:[', 'inner:a', 'inner:;', 'main:b'], run_modes, cascade_lexer(consume=False), '<[a;b')
utest_seq(['main:<', 'outer:[', 'inner:a', 'inner:;', 'outer:b', 'outer:;', 'main:c'], run_modes, cascade_lexer(consume=True), '<[a;b;c')


# Transition definition errors.

ab_modes = [LexMode('main', ['a', 'b']), LexMode('sub', ['a', 'b'])]

utest_exc(Lexer.DefinitionError("expected `LexTrans`; received 'x'"), Lexer, patterns=ab_patterns, modes=ab_modes, transitions=['x'])

utest_exc(Lexer.DefinitionError("unknown parent mode: 'nope'"),
  Lexer, patterns=ab_patterns, modes=ab_modes, transitions=[LexTrans('nope', kind='a', mode='sub', pop='b', consume=True)])

utest_exc(Lexer.DefinitionError("unknown child mode: 'nope'"),
  Lexer, patterns=ab_patterns, modes=ab_modes, transitions=[LexTrans('main', kind='a', mode='nope', pop='b', consume=True)])

utest_exc(Lexer.DefinitionError("unknown mode push pattern: 'c'"),
  Lexer, patterns=ab_patterns, modes=ab_modes, transitions=[LexTrans('main', kind='c', mode='sub', pop='b', consume=True)])

utest_exc(Lexer.DefinitionError("unknown mode pop pattern: 'c'"),
  Lexer, patterns=ab_patterns, modes=ab_modes, transitions=[LexTrans('main', kind='a', mode='sub', pop='c', consume=True)])

utest_exc(Lexer.DefinitionError("conflicting transitions:\n"
  "  LexTrans(('main',), kind=('a',), mode='sub', pop=['b'], consume=True)\n"
  "  LexTrans(('sub', 'main'), kind=('b', 'a'), mode='main', pop=['a'], consume=False)"),
  Lexer, patterns=ab_patterns, modes=ab_modes, transitions=[
    LexTrans('main', kind='a', mode='sub', pop='b', consume=True),
    LexTrans(('sub', 'main'), kind=('b', 'a'), mode='main', pop='a', consume=False)])


# Line-aware modes.

line_lexer = Lexer(patterns=dict(newline=r'\n', spaces=r' +', word=r'\w+', paren_o=r'\(', paren_c=r'\)'),
  modes=[
    LexMode('main', ['newline', 'spaces', 'word', 'paren_o'], line_break_kind='newline'),
    LexMode('group', ['newline', 'spaces', 'word', 'paren_c'])],
  transitions=[
    LexTrans('main', kind='paren_o', mode='group', pop='paren_c', consume=True)])

# An empty `end_of_line` precedes the line break of each line that holds another token, and ends an unterminated last line.
utest_seq([('word', 'a'), ('end_of_line', ''), ('newline', '\n'), ('newline', '\n'), ('word', 'b'), ('end_of_line', '')],
  run_lexer, line_lexer, 'a\n\nb')

# Without a declared ignore set, a line of only spaces counts.
utest_seq([('spaces', ' '), ('end_of_line', ''), ('newline', '\n')], run_lexer, line_lexer, ' \n')

# A pushed mode that is not line-aware suspends the rule; the line ends at the next line break in the line-aware mode.
utest_seq(['main:a', 'main:(', 'group:b', 'group:\n', 'group:c', 'group:)', 'main:', 'main:\n', 'main:d', 'main:'],
  run_modes, line_lexer, 'a(b\nc)\nd')

# The synthesized token honors `drop`, and the line break can be dropped independently.
utest_seq([('word', 'a'), ('newline', '\n')], run_lexer, line_lexer, 'a\n', drop={'end_of_line'})
utest_seq([('word', 'a'), ('end_of_line', '')], run_lexer, line_lexer, 'a\n', drop={'newline'})

utest_exc(Lexer.DefinitionError("mode 'main' line_break_kind is not a pattern of the mode: 'nl'"),
  Lexer, patterns=dict(a='a'), modes=[LexMode('main', ['a'], line_break_kind='nl')])

utest_exc(Lexer.DefinitionError("name is reserved: 'end_of_line'"), Lexer, patterns=dict(end_of_line='a'))


# Indents.

indent_patterns = dict(
  newline = r'\n',
  spaces = r' +',
  word = r'\w+',
  comment = r'\#[^\n]*',
  paren_o = r'\(',
  paren_c = r'\)')

indent_lexer = Lexer(patterns=indent_patterns,
  modes=[
    LexMode('main', ['newline', 'spaces', 'word', 'comment', 'paren_o'], indents=True),
    LexMode('group', ['newline', 'spaces', 'word', 'paren_c'])],
  transitions=[
    LexTrans('main', kind='paren_o', mode='group', pop='paren_c', consume=True)])


def run_indents(string:str, **kwargs:Any) -> Iterator[str]:
  'Run `indent_lexer` on `string`, yielding the text of each word and the kind of each other token. Spaces are dropped.'
  source = Source(name='test', text=string)
  for token in indent_lexer.lex(source, drop={'spaces'}, **kwargs):
    yield source[token] if token.kind == 'word' else token.kind


utest_seq(['a', 'newline', 'indent', 'b', 'newline', 'indent', 'c', 'newline', 'dedent', 'd', 'newline', 'dedent', 'e', 'newline'],
  run_indents, 'a\n  b\n    c\n  d\ne\n')

# A dedent can close several levels.
utest_seq(['a', 'newline', 'indent', 'b', 'newline', 'indent', 'c', 'newline', 'dedent', 'dedent', 'd'],
  run_indents, 'a\n  b\n    c\nd')

# The start of the range is the start of a line.
utest_seq(['indent', 'a', 'newline', 'dedent', 'b'], run_indents, '  a\nb')

# Empty lines and lines of only spaces do not affect the indentation.
utest_seq(['a', 'newline', 'indent', 'b', 'newline', 'newline', 'newline', 'c', 'newline', 'newline', 'dedent', 'd'],
  run_indents, 'a\n  b\n\n \n  c\n      \nd')

# Open levels are closed at the end, after trailing spaces.
utest_seq(['a', 'newline', 'indent', 'b', 'dedent'], run_indents, 'a\n  b')
utest_seq(['a', 'newline', 'indent', 'b', 'newline', 'dedent', 'end_of_text'], run_indents, 'a\n  b\n    ', eot=True)

# A pushed mode that lacks `indents` suspends the indentation rules, but its newlines still begin lines for the parent.
utest_seq(['a', 'newline', 'indent', 'paren_o', 'b', 'newline', 'c', 'newline', 'paren_c', 'newline', 'd', 'newline', 'dedent', 'e'],
  run_indents, 'a\n  (b\n      c\n)\n  d\ne')
#^ The `paren_c` at column 0 is in the `group` mode, so it does not dedent.

# Limitation: a line that holds only a comment affects the indentation like any other line.
utest_seq(['a', 'newline', 'indent', 'b', 'newline', 'dedent', 'comment', 'newline', 'indent', 'c', 'dedent'],
  run_indents, 'a\n  b\n# x\n  c')

# Limitation: a dedent to a width that is not an open level closes the deeper levels and opens a new one, without an error.
utest_seq(['a', 'newline', 'indent', 'b', 'newline', 'dedent', 'indent', 'c', 'dedent'], run_indents, 'a\n    b\n  c')


def indent_positions(string:str) -> list[tuple[str,int,int]]:
  'Return (kind, pos, end) for each `indent` and `dedent` token.'
  tokens = indent_lexer.lex(Source(name='test', text=string))
  return [(t.kind, t.pos, t.end) for t in tokens if t.kind in ('indent', 'dedent')]

# The synthesized tokens are empty. An `indent` precedes the spaces of its line; a `dedent` precedes the first token of its line.
utest([('indent', 2, 2), ('dedent', 6, 6), ('indent', 8, 8), ('dedent', 12, 12)], indent_positions, 'a\n  b\nc\n  d\n')
#^ The final `dedent` is at the end of the text.

# The `spaces` token follows its `indent`, and precedes a `dedent` to a nonzero level.
utest_seq([('word', 'a'), ('newline', '\n'), ('indent', ''), ('spaces', '  '), ('word', 'b'), ('newline', '\n'),
  ('indent', ''), ('spaces', '    '), ('word', 'c'), ('newline', '\n'), ('dedent', ''), ('spaces', '  '), ('word', 'd'), ('dedent', '')],
  run_lexer, indent_lexer, 'a\n  b\n    c\n  d')


# Indent definition errors.

utest_exc(Lexer.DefinitionError("mode 'main' has indents but lacks the 'newline' pattern"),
  Lexer, patterns=ab_patterns, modes=[LexMode('main', ['a'], indents=True)])

utest_exc(Lexer.DefinitionError("'indent' pattern name collides with the indent token name"),
  Lexer, patterns=dict(newline='\n', spaces=' +', indent='>'), modes=[LexMode('main', ['newline', 'spaces', 'indent'], indents=True)])

# The synthesized tokens do not take part in transitions.
utest_exc(Lexer.DefinitionError("unknown mode push pattern: 'indent'"),
  Lexer, patterns=dict(newline='\n', spaces=' +'),
  modes=[LexMode('main', ['newline', 'spaces'], indents=True), LexMode('sub', ['newline'])],
  transitions=[LexTrans('main', kind='indent', mode='sub', pop='newline', consume=True)])
