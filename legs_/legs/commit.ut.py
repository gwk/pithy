# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Commitment syntax, fallback, minimization and generated Python behavior.'

from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory
from typing import cast

from legs import DictLexerBase
from legs.build import build_lexer_class, build_lexer_class_for_automata, build_mode_automata
from legs.parse import parse_legs
from legs.props import GrammarChecker
from legs.targets.python import output_python
from tolkien import Source
from utest import utest_run, utest_val


def check(grammar_text:str, cases:dict[bytes,list[tuple[str,bytes]]]) -> None:
  grammar = parse_legs('commit-test', grammar_text)
  automata = list(build_mode_automata(grammar))
  lexer = build_lexer_class_for_automata('CommitLexer', grammar, iter(automata))
  with TemporaryDirectory() as directory:
    path = str(Path(directory) / 'lexer.py')
    output_python(path, [a.min_dfa for a in automata], grammar.transitions, grammar.mode_line_breaks, grammar.mode_line_ignores,
      grammar.mode_indent_spaces, lexer.pattern_descs,
      grammar.license, patterns_path=None, type_prefix='Commit')
    generated = cast(type[DictLexerBase], run_path(path)['CommitLexer'])
    for text, expected in cases.items():
      source = Source('test', text)
      for cls in (lexer, generated):
        utest_val(expected, [(t.kind, text[t.slc]) for t in cls(source)], repr(text))
      GrammarChecker(grammar, automata, lexer).check_tokens(text, 'main')
  GrammarChecker(grammar, automata, lexer).check_all(max_examples=20)


@utest_run
def numbers() -> None:
  check(r'''
number: $Dec ($Dec | _, $Dec)* ([e E], [\+ \-]? $Dec ($Dec | _, $Dec)*)?
  | 0 [x X], _? $Hex ($Hex | _, $Hex)*
name: $Ascii_Letter+
plus: \+
comma: [,]
''', {
    b'0': [('number', b'0')],
    b'0x': [('incomplete', b'0x')],
    b'0xG': [('incomplete', b'0x'), ('name', b'G')],
    b'0x12+': [('number', b'0x12'), ('plus', b'+')],
    b'0x12_': [('incomplete', b'0x12_')],
    b'0x12_G': [('incomplete', b'0x12_'), ('name', b'G')],
    b'1e+': [('incomplete', b'1e+')],
    b'1e+G': [('incomplete', b'1e+'), ('name', b'G')],
    b'1_': [('incomplete', b'1_')],
    b'1e2+0': [('number', b'1e2'), ('plus', b'+'), ('number', b'0')],
    b'123abc': [('number', b'123'), ('name', b'abc')],
    b'0x12Z': [('number', b'0x12'), ('name', b'Z')],
    b',': [('comma', b',')],
  })


@utest_run
def preserve_barriers_during_minimization() -> None:
  check('short: a | b\nlong: a x, y | b x y\nname: [x y z]+\n', {
    b'axz': [('incomplete', b'ax'), ('name', b'z')],
    b'bxz': [('short', b'b'), ('name', b'xz')],
    b'axy': [('long', b'axy')],
    b'bxy': [('long', b'bxy')],
  })


@utest_run
def competing_rules_and_later_fallback() -> None:
  check('short: a\nsame: ab\nlong: ab, cde\nother: abx\n', {
    b'ab!': [('same', b'ab'), ('invalid', b'!')],
    b'abc!': [('same', b'ab'), ('invalid', b'c!')],
    b'abx': [('other', b'abx')],
    b'abcde': [('long', b'abcde')],
  })
  check('short: a\nlong: ab, c (de)?\n', {
    b'ab!': [('incomplete', b'ab'), ('invalid', b'!')],
    b'abcd!': [('long', b'abc'), ('invalid', b'd!')],
  })


@utest_run
def modes_slices_and_literal_commas() -> None:
  grammar = parse_legs('test', r'''
open: \(
close: \)
comma: \,
num: $Dec+ | 0x, $Hex+
# Modes

## main
kinds: open comma

## inner
kinds: close num comma
# Transitions
main : open :: inner : close
''')
  lexer = build_lexer_class('Test', grammar)
  source = Source('test', b'(0x),')
  utest_val([('main', 'open', 0, 1), ('inner', 'incomplete', 1, 3), ('inner', 'close', 3, 4), ('main', 'comma', 4, 5)],
    [(t.mode, t.kind, t.pos, t.end) for t in lexer(source)])
  source = Source('test', b'0x12')
  utest_val([('incomplete', 0, 2)], [(t.kind, t.pos, t.end) for t in lexer(source, slice(0, 2), mode='inner')])
  check('short: $Ll\nlong: $Ll x, y\n', {
    'éx'.encode(): [('incomplete', 'éx'.encode())],
    'éxy'.encode(): [('long', 'éxy'.encode())],
  })
