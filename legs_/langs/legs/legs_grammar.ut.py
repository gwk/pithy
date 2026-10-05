# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Test `legs.legs`, the legs lexer for the contents of legs grammar files.

This demonstrates the use of a legs lexer within a parser that frames the text by line shape:
`pithy.sectsyn` splits a grammar file into sections and entries, and each entry is lexed in the mode for its section.
The resulting tokens are compared to those of the handwritten `pithy.lex` lexers that `legs.parse` uses.
'''

from os.path import dirname
from typing import Iterator

from legs.cache import cached_lexer_class
from legs.parse import build_pattern_parser, decl_lexer, pattern_head_re, pattern_lexer, pattern_parser
from pithy.lex import Lexer
from pithy.parse import ParseError
from pithy.sectsyn import parse_entries, parse_sections
from tolkien import Source
from utest import utest, utest_exc, utest_seq_exc, utest_val


repo_dir = dirname(dirname(dirname(dirname(__file__))))
grammar_path = f'{repo_dir}/legs_/langs/legs/legs.legs'

LegsLexer = cached_lexer_class(grammar_path, f'{repo_dir}/_build/langs/legs.py')

type Tokens = list[tuple[str,str,str]] # (mode, kind, text).


def framed_ranges(source:Source[str]) -> Iterator[tuple[str,slice]]:
  'Yield the start mode and range of each lexable part of a legs grammar file.'
  name = 'patterns' # Text preceding the first header is treated as patterns.
  for sect in parse_sections(source, symbol='#', numbered=False, title_sep=':', raises=True):
    if sect.level == 1: name = source[sect.name].partition('//')[0].strip().lower()
    elif sect.level == 2: assert name == 'modes' # A mode subsection; its entries are lexed like those of its parent.
    if name == 'patterns':
      for entry in parse_entries(source, sect.raw_body, continuations=['|'], comments=['//'], raises=True):
        m = pattern_head_re.match(source.text, entry.start, entry.stop)
        assert m is not None
        if m['colon']: yield ('pattern', slice(m.end(), entry.stop)) # A bare name has no pattern expression.
    elif name in ('modes', 'transitions'):
      for entry in parse_entries(source, sect.raw_body, comments=['//'], raises=True):
        yield ('decl', entry)


def legs_tokens(text:str, mode:str, slc:slice|None=None) -> Tokens:
  'Lex with the legs lexer. The text must be ASCII so that the byte positions equal the character positions.'
  source = Source('test', text.encode('ascii'))
  return [(t.mode, t.kind, source[t]) for t in LegsLexer(source, slc, mode=mode)]


def handwritten_tokens(text:str, mode:str, slc:slice|None=None) -> Tokens:
  source = Source('test', text)
  lexer:Lexer = decl_lexer if mode == 'decl' else pattern_lexer
  return [(mode if t.mode == 'main' else t.mode, t.kind, source[t]) for t in lexer.lex(source, slc)]


# `pithy.parse.Parser` accepts a legs lexer class in place of a `pithy.lex.Lexer`; the start mode is passed to `parse`.
legs_pattern_parser = build_pattern_parser(LegsLexer)

def legs_regex(text:str, slc:slice|None=None) -> str:
  'Parse a pattern expression using the legs lexer and return its regex.'
  pattern = legs_pattern_parser.parse('pattern_expr', Source('test', text.encode('ascii')), slc=slc, mode='pattern')
  return str(pattern.gen_regex(flavor='py.re'))

def handwritten_regex(text:str, slc:slice|None=None) -> str:
  return str(pattern_parser.parse('pattern_expr', Source('test', text), slc=slc).gen_regex(flavor='py.re'))

utest(handwritten_regex('a b+ [c d e - [d]] | f // Comment.'), legs_regex, 'a b+ [c d e - [d]] | f // Comment.')
utest('ab+[ce]|f', legs_regex, 'a b+ [c d e - [d]] | f // Comment.')
utest('x', legs_regex, 'a: [\nb: x\n', slice(8, 9))
utest_exc(ParseError, legs_regex, 'a [b')


# Code point escapes lex the same way in both lexers; an incomplete escape lexes as a single character escape.
code_escapes = '\\41/\\e9/\\f/\\f[\\1F600/\\4\\200D\\1234567/]'
utest(handwritten_tokens(code_escapes, 'pattern', None), legs_tokens, code_escapes, 'pattern')

# The start mode selects the syntax.
utest([('decl', 'sym', 'ab'), ('decl', 'colon', ':'), ('decl', 'spaces', ' '), ('decl', 'sym', 'c')],
  legs_tokens, 'ab: c', 'decl')

utest([
  ('pattern', 'char', 'a'), ('pattern', 'char', 'b'), ('pattern', 'plus', '+'), ('pattern', 'spaces', ' '),
  ('pattern', 'brack_o', '['), ('charset', 'charset_char', 'a'), ('charset', 'dash', '-'), ('charset', 'brack_o', '['),
  ('charset', 'ref', '$B'), ('charset', 'brack_c', ']'), ('charset', 'charset_char', '|'), ('charset', 'brack_c', ']'),
  ('pattern', 'char', '-'), ('pattern', 'esc', '\\#'), ('pattern', 'spaces', ' '), ('pattern', 'comment', '// c')],
  legs_tokens, 'ab+ [a-[$B]|]-\\# // c', 'pattern')

# An unknown start mode is an error. The grammar has no `main` mode, so the start mode must be specified.
unknown_mode_exc = ValueError("unknown mode: 'main'; modes: ['charset', 'decl', 'pattern']")
utest_exc(unknown_mode_exc, legs_tokens, 'a', 'main')
utest_exc(unknown_mode_exc, LegsLexer, Source('test', b'a'))
utest_seq_exc(unknown_mode_exc, LegsLexer.lex, Source('test', b'a'))

# The range confines the lexer; an unclosed charset does not affect the lexing of a following range.
utest([('pattern', 'brack_o', '['), ('charset', 'charset_char', 'x')], legs_tokens, 'a: [x\nb: y\n', 'pattern', slice(3, 5))
utest([('pattern', 'char', 'y')], legs_tokens, 'a: [x\nb: y\n', 'pattern', slice(9, 10))


# The legs lexer produces the same tokens as the handwritten lexers for every framed range of every grammar file.
grammar_paths = [grammar_path, f'{repo_dir}/legs_/langs/ascii/ascii.legs', f'{repo_dir}/legs_/test/0/basic.legs',
  f'{repo_dir}/legs_/test/0/modes.legs', f'{repo_dir}/legs_/test/0/parsing.legs', f'{repo_dir}/wu_/wu/writeup.legs']

for path in grammar_paths:
  with open(path) as f: text = f.read()
  ranges = list(framed_ranges(Source(path, text)))
  utest_val(True, bool(ranges), f'has ranges: {path}')
  for mode, slc in ranges:
    utest(handwritten_tokens(text, mode, slc), legs_tokens, text, mode, slc, _utest_label=path)
    if mode == 'pattern':
      utest(handwritten_regex(text, slc), legs_regex, text, slc, _utest_label=path)


# The generated grammar lexer recognizes commitment only outside character sets.
utest([('pattern', 'char', 'a'), ('pattern', 'commit', ','), ('pattern', 'char', 'b'),
  ('pattern', 'brack_o', '['), ('charset', 'charset_char', ','), ('charset', 'brack_c', ']')],
  legs_tokens, 'a,b[,]', 'pattern')
