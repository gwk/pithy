#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from difflib import unified_diff
from os.path import dirname, join as path_join
from subprocess import PIPE, run, STDOUT
from sys import executable as python_path, stderr
from tempfile import TemporaryDirectory
from typing import Callable

from pithy.cmdparse import Cmd, flag, opt, pos
from pithy.fs import make_dirs
from pithy.strings import pluralize
from tolkien import Source

from ..build import build_lexer_class, build_mode_automata, build_pattern_descs
from ..dfa import DFA
from ..parse import Grammar, parse_legs
from ..patterns import gen_incomplete_pattern
from ..props import GrammarChecker, PropertyError
from ..python import output_python, output_python_re
from ..swift import output_swift, swift_kind_syms, swift_safe_sym


default_langs = ['python', 'swift']


def main() -> None: LegsTestCmd.main()



class LegsTestCmd(Cmd):
  '''
  Test the lexers generated from a legs grammar.

  Each input string is lexed by a reference lexer that is built in-process, and the resulting tokens are printed.
  Each token line consists of the byte range, the token kind and the token text.
  Then for each language, the lexer source code is generated and run on the same inputs.
  If the tokens of a generated lexer differ from those of the reference lexer,
  then the differences are reported and the exit code is 1.

  With `-props`, the reference lexer is also checked against the NFA of each mode, using inputs generated from the grammar.
  See `legs.props` for the properties. If no inputs are given then the lexer sources are not generated.
  '''

  cmd_name = 'legs-test'

  path:str = pos(doc='Path to the .legs file.')
  inputs:list[str] = pos(default_factory=list, metavar='INPUT',
    doc='A string to lex. Write `--` before inputs that begin with a dash.')
  build_dir:str|None = opt(default=None,
    doc='Directory in which to keep the generated sources; defaults to a temporary directory.')
  langs:list[str] = opt(default_factory=list, metavar='LANG', split=',',
    doc=f'Languages of the generated lexers to test, separated by commas. Defaults to {",".join(default_langs)}.')
  mode:str = opt(default='main', doc='Mode in which lexing starts.')
  props:bool = flag(doc='Check the properties of the reference lexer using generated inputs.')
  examples:int = opt(default=100, doc='The number of examples to generate per pattern and per mode for `-props`.')
  randomize:bool = flag(doc='Generate different examples on each run of `-props`; by default the examples are repeatable.')
  stats:bool = flag(doc='Print the number of inputs checked by `-props`.')


  def run(self) -> None:
    if not (self.inputs or self.props): exit('error: no inputs; specify input strings or `-props`.')
    langs = self.langs or default_langs
    for lang in langs:
      if lang not in lang_runners: exit(f'error: unknown language {lang!r}; testable languages: {", ".join(lang_runners)}.')

    try: f = open(self.path)
    except FileNotFoundError: exit(f'error: no such grammar file: {self.path!r}')
    with f: grammar = parse_legs(self.path, f.read())
    if self.inputs and self.mode not in grammar.modes:
      exit(f'error: grammar has no mode named {self.mode!r}; specify the start mode with `-mode`. '
        f'modes: {", ".join(sorted(grammar.modes))}.')

    try: automata = list(build_mode_automata(grammar))
    except ValueError as e: exit(str(e))
    dfas = [a.min_dfa for a in automata]

    if self.props:
      checker = GrammarChecker(grammar, automata)
      try: props_stats = checker.check_all(max_examples=self.examples, derandomize=not self.randomize)
      except PropertyError as e: exit(f'error: property violated: {e}')
      print(f'properties hold for {pluralize(len(automata), "mode")}.')
      if self.stats: print(props_stats)
    if not self.inputs: return

    test = LexerTest(grammar=grammar, dfas=dfas, mode=self.mode, inputs=[s.encode() for s in self.inputs])
    reference = test.reference_tokens()
    for text, tokens in zip(test.inputs, reference):
      print(f'\n{text.decode()!r}:')
      for line in token_lines(text, tokens): print(line)

    with TemporaryDirectory() as temp_dir:
      build_dir = self.build_dir or temp_dir
      make_dirs(build_dir)
      ok = True
      for lang in langs:
        ok &= test.compare(lang, reference, lang_runners[lang](test, path_join(build_dir, 'test_lexer')))
    if not ok: exit(1)



type Tokens = list[tuple[str,int,int]] # (kind, pos, end).


class LexerTest:
  'The grammar, start mode and inputs of a test, with the means to lex the inputs with each kind of lexer.'

  def __init__(self, grammar:Grammar, dfas:list[DFA], mode:str, inputs:list[bytes]):
    self.grammar = grammar
    self.dfas = dfas
    self.mode = mode
    self.inputs = inputs
    self.pattern_descs = build_pattern_descs(grammar)


  def reference_tokens(self) -> list[Tokens]:
    'Lex each input with a lexer built in-process from the grammar.'
    Lexer = build_lexer_class('ReferenceLexer', self.grammar)
    return [[(t.kind, t.pos, t.end) for t in Lexer(Source('input', text), mode=self.mode)] for text in self.inputs]


  def compare(self, lang:str, reference:list[Tokens], actual:list[Tokens]) -> bool:
    'Report any differences between the reference tokens and those of the generated lexer; return True if there are none.'
    ok = True
    for text, ref_tokens, act_tokens in zip(self.inputs, reference, actual, strict=True):
      if ref_tokens == act_tokens: continue
      ok = False
      print(f'\n{lang}: tokens differ from the reference lexer for input {text.decode()!r}:', file=stderr)
      diff = unified_diff(token_lines(text, ref_tokens), token_lines(text, act_tokens), 'reference', lang, lineterm='')
      for line in diff: print(line, file=stderr)
    return ok


  def run_python(self, stem:str) -> list[Tokens]:
    path = stem + '.py'
    output_python(path, dfas=self.dfas, mode_transitions=self.grammar.transitions, pattern_descs=self.pattern_descs,
      license=self.grammar.license, patterns_path=None, type_prefix='')
    return self.run_python_driver(path)


  def run_python_re(self, stem:str) -> list[Tokens]:
    path = stem + '.re.py'
    patterns = self.grammar.patterns
    incomplete_patterns = {dfa.name: gen_incomplete_pattern(dfa.backtracking_order, patterns) for dfa in self.dfas}
    output_python_re(path, dfas=self.dfas, mode_transitions=self.grammar.transitions, patterns=patterns,
      incomplete_patterns=incomplete_patterns, pattern_descs=self.pattern_descs, license=self.grammar.license,
      patterns_path=None, type_prefix='')
    return self.run_python_driver(path)


  def run_python_driver(self, path:str) -> list[Tokens]:
    with open(path, 'a') as f: f.write(python_driver)
    return self.run_driver([python_path, path, self.mode], kind_for_field=str)


  def run_swift(self, stem:str) -> list[Tokens]:
    path = stem + '.swift'
    output_swift(path, dfas=self.dfas, mode_transitions=self.grammar.transitions, pattern_descs=self.pattern_descs,
      license=self.grammar.license, patterns_path=None, type_prefix='')
    # Append the base source and the driver, because `swift` interprets a single file.
    with open(path_join(dirname(dirname(__file__)), 'legs_base.swift')) as f: base = f.read()
    with open(path, 'a') as f:
      f.write('\n\n')
      f.write(base)
      f.write(swift_driver.replace('${mode}', swift_safe_sym(self.mode)))
    # The Swift driver prints the raw value of each token kind. The enum cases are declared in sorted order of their names.
    kind_syms = swift_kind_syms(self.pattern_descs)
    kinds = sorted(kind_syms, key=lambda kind: kind_syms[kind])
    return self.run_driver(['swift', path], kind_for_field=lambda field: kinds[int(field)])


  def run_driver(self, cmd:list[str], kind_for_field:Callable[[str],str]) -> list[Tokens]:
    '''
    Run a driver on the inputs and parse its output.
    A driver prints one line per token, consisting of the kind, position and end separated by tabs.
    It prints an empty line after the tokens of each input.
    '''
    proc = run([*cmd, *(text.decode() for text in self.inputs)], stdout=PIPE, stderr=STDOUT, text=True)
    if proc.returncode != 0: exit(f'error: test lexer failed: {" ".join(cmd)}\n{proc.stdout}')
    results:list[Tokens] = [[]]
    for line in proc.stdout.splitlines():
      if not line:
        results.append([])
        continue
      kind_field, pos, end = line.split('\t')
      results[-1].append((kind_for_field(kind_field), int(pos), int(end)))
    assert results.pop() == [], 'driver output does not end with an empty line.'
    return results



def token_lines(text:bytes, tokens:Tokens) -> list[str]:
  return [f'{pos}-{end} {kind} {text[pos:end].decode(errors="replace")!r}' for kind, pos, end in tokens]


lang_runners:dict[str,Callable[[LexerTest,str],list[Tokens]]] = {
  'python': LexerTest.run_python,
  'python-re': LexerTest.run_python_re,
  'swift': LexerTest.run_swift,
}


python_driver = '''

if __name__ == '__main__':
  from sys import argv
  from tolkien import Source
  for arg in argv[2:]:
    for token in Lexer(Source('input', arg.encode()), mode=argv[1]): print(token.kind, token.pos, token.end, sep='\\t')
    print()
'''


swift_driver = r'''

// Legs test driver.

for (i, arg) in CommandLine.arguments.enumerated() {
  if i == 0 { continue }
  let source = Source(name: "input", text: Array(arg.utf8))
  for token in Lexer(source: source, mode: .${mode}) {
    print("\(token.kind.rawValue)\t\(token.pos)\t\(token.end)")
  }
  print("")
}
'''


if __name__ == '__main__': main()
