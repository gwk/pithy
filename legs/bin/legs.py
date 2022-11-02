#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser

from pithy.io import errL, errLL, errSL, errZ, outL, outZ
from pithy.iterable import first_el
from pithy.path import path_ext, path_join, path_name, split_dir_name
from pithy.string import pluralize

from ..build import build_dfa, build_nfa
from ..dfa import DFA, minimize_dfa
from ..dot import output_dot
from ..nfa import NFA
from ..parse import parse_legs
from ..patterns import LegsPattern, gen_incomplete_pattern
from ..python import output_python, output_python_re
from ..swift import output_swift
from ..vscode import output_vscode


description = '''
Legs is a lexer generator: it takes as input a `.legs` grammar file,
and outputs code that tokenizes text, converting a stream of characters into a stream of chunks of text called tokens.

The grammar file defines the kinds of tokens and the patterns of text that they match.
The patterns are similar to regular expressions but with several important differences:
* character classes are specified using their Unicode names. (TODO: provide documentation)
* the pattern language is limited to the semantics of formal regular languages.

There are two special token kinds:
* `invalid` indicates a sequence of bytes for which the lexer could not start matching;
* `incomplete` indicating a token that began to match but did not complete.
This distinction is important for error reporting;
lexical errors are found at the ends of `incomplete` tokens and the starts of `invalid` tokens.
'''


def main() -> None:
  parser = ArgumentParser(prog='legs', description=description)
  parser.add_argument('path', nargs='?', help='Path to the .legs file.')
  parser.add_argument('-dbg', action='store_true', help='Verbose debug printing.')
  parser.add_argument('-describe', action='store_true', help='Print pattern descriptions.')
  parser.add_argument('-encoding', default='utf-8', help='Encoding of the input file.')
  parser.add_argument('-langs', nargs='+', default=[], help='Target languages for which to generate lexers.')
  parser.add_argument('-match', nargs='+', help='Attempt to lex each argument string.')
  parser.add_argument('-mode', default=None, help='Mode with which to lex the arguments to `-match`.')
  parser.add_argument('-output', default=None, help='Path to output generated source.')
  parser.add_argument('-patterns', nargs='+', help='Specify legs patterns for quick testing.')
  parser.add_argument('-stats', action='store_true', help='Print statistics about the generated automata.')
  parser.add_argument('-syntax-exts', nargs='*', help='Extensions list for syntax definitions.')
  parser.add_argument('-syntax-name', help='Syntax readable name for syntax definitions.')
  parser.add_argument('-syntax-scope', help='Syntax scope name for textmate-style syntax definitions.')

  parser.add_argument('-test', nargs='+',
    help='Generate testing source code for the specified language or else all supported languages;'
    ' run each test lexer on the specified arguments.')

  parser.add_argument('-type-prefix', default='', help='Type names prefix for generated source code.')

  args = parser.parse_args()
  dbg = args.dbg

  if not args.match and args.mode:
    exit('`-mode` option only valid with `-match`.')
  match_mode = args.mode or 'main'

  if args.match and args.output: exit('`-match` and `-output` are mutually exclusive.')
  if args.match and args.langs: exit('`-match` and `-langs` are mutually exclusive.')
  if args.match and args.test: exit('`-match` and `-test` are mutually exclusive.')

  langs:set[str] = determine_output_languages(args.langs, is_test=bool(args.test), output_path=args.output)

  # Get the source string from either the command line or the source file.
  if (args.path is None) and args.patterns:
    path = '<patterns>'
    src = '\n'.join(args.patterns)
  elif (args.path is not None) and not args.patterns:
    path = args.path
    try: src = open(path).read()
    except FileNotFoundError:
      exit(f'legs error: no such pattern file: {path!r}')
  else:
    exit('`must specify either `path` or `-patterns`.')

  grammar = parse_legs(path, src)
  license = grammar.license
  patterns = grammar.patterns
  mode_pattern_kinds = grammar.modes
  mode_transitions = grammar.transitions

  if dbg:
    errSL('\nPatterns:')
    for name, pattern in patterns.items():
      pattern.describe(name=name)
    errL()

  dfas:list[DFA] = []
  start_node = 0
  for mode, pattern_kinds in sorted(mode_pattern_kinds.items(), key=lambda p: mode_name_key(p[0])):
    if args.match and mode != match_mode: continue

    named_patterns = sorted((kind, patterns[kind]) for kind in pattern_kinds)
    nfa = build_nfa(name=mode, named_patterns=named_patterns, encoding=args.encoding)
    if dbg: nfa.describe('NFA')
    if dbg or args.stats: nfa.describe_stats(f'NFA Stats')
    msgs = nfa.validate()
    if msgs:
      errLL(*msgs)
      exit(1)

    fat_dfa = build_dfa(nfa)
    if dbg: fat_dfa.describe('Fat DFA')
    if dbg or args.stats: fat_dfa.describe_stats('Fat DFA Stats')

    min_dfa = minimize_dfa(fat_dfa, start_node=start_node)
    start_node = min_dfa.end_node
    if dbg: min_dfa.describe('Min DFA')
    if dbg or args.stats: min_dfa.describe_stats('Min DFA Stats')
    dfas.append(min_dfa)

    if dbg: errL('----')

    post_matches = len(min_dfa.post_match_nodes)
    if post_matches:
      errL(f'note: `{mode}`: minimized DFA contains ', pluralize(post_matches, "post-match node"), '.')

  # If we are testing patterns on the command line, then find the specified DFA, test each argument, and exit.
  if args.match:
    for dfa in dfas:
      if dfa.name != mode: continue
      for text in args.match:
        text_bytes = text.encode(args.encoding)
        match_bytes(nfa, fat_dfa, min_dfa, text, text_bytes)
      exit()
    exit(f'bad mode: {match_mode!r}')

  pattern_descs = { name : pattern.literal_desc or name for name, pattern in patterns.items() }
  pattern_descs.update((n, n) for n in ['invalid', 'incomplete'])

  incomplete_patterns:dict[str,LegsPattern|None] = {
    dfa.name : gen_incomplete_pattern(dfa.backtracking_order, patterns) for dfa in dfas }

  if args.describe:
    errL('Patterns:')
    for name, pattern in patterns.items():
      pattern.describe(name=name)
    for name, inc_pattern in incomplete_patterns.items():
      if inc_pattern:
        inc_pattern.describe(name=f'{name}.incomplete')

  if not (langs or args.test): exit(0)

  out_path = args.output or args.path
  if not out_path: exit('`-path` or `-output` most be specified to determine output paths.')

  test_cmds:list[list[str]] = []

  out_dir, out_name = split_dir_name(out_path)
  if not out_name:
    if not args.path: exit('could not determine output file name.')
    out_name = path_name(args.path)
    if not out_name: exit('could not determine output file name from `path`.')
  out_name_stem = out_name[:out_name.find('.')] if '.' in out_name else out_name # TODO: path_stem should be changed to do this.
  out_stem = path_join(out_dir, out_name_stem)

  if 'dot' in langs:
    output_dot(out_stem, dfas=dfas,
      pattern_descs=pattern_descs, license=license, args=args)

  if 'python' in langs:
    path = out_stem + '.py'
    output_python(path, dfas=dfas, mode_transitions=mode_transitions,
      pattern_descs=pattern_descs, license=license, args=args)
    if args.test: test_cmds.append(['python3', path] + args.test)

  if 'python-re' in langs:
    path = out_stem + '.re.py'
    output_python_re(path, dfas=dfas, mode_transitions=mode_transitions,
      patterns=patterns, incomplete_patterns=incomplete_patterns,
      pattern_descs=pattern_descs, license=license, args=args)
    if args.test: test_cmds.append(['python3', path] + args.test)

  if 'swift' in langs:
    path = out_stem + '.swift'
    output_swift(path, dfas=dfas, mode_transitions=mode_transitions,
      pattern_descs=pattern_descs, license=license, args=args)
    if args.test: test_cmds.append(['swift', path] + args.test)

  if 'vscode' in langs:
    path = out_stem + '.json'
    output_vscode(path, dfas=dfas, mode_transitions=mode_transitions,
      patterns=patterns, incomplete_patterns=incomplete_patterns,
      pattern_descs=pattern_descs, license=license, args=args)

  if args.test:
    run_tests(test_cmds, dbg=args.dbg)



def determine_output_languages(args_langs:list[str], is_test:bool, output_path:str|None) -> set[str]:
  if args_langs:
    if 'all' in args_langs:
      langs = supported_langs
    else:
      for lang in args_langs:
        if lang not in supported_langs:
          exit(f'unknown language {lang!r}; supported languages are: {sorted(supported_langs)}.')
      langs = set(args_langs)
  elif is_test:
    langs = test_langs
  elif output_path:
    ext = path_ext(output_path)
    try: langs = {ext_langs[ext]}
    except KeyError:
      exit(f'unsupported output language extension {ext!r}; supported extensions are: {sorted(ext_langs)}.')
  else:
    langs = set()
  return langs


def mode_name_key(name:str) -> str:
  'Always place main mode first.'
  return '' if name == 'main' else name


def run_tests(test_cmds:list[list[str]], dbg:bool) -> None:
  # For each language, run against the specified match arguments, and capture output.
  # Print the output from the first test, and then the diff for each subsequent output that differs.
  from difflib import ndiff
  from shlex import quote as sh_quote

  from pithy.task import runCO

  def quote(cmd:list[str]) -> str: return ' '.join(sh_quote(arg) for arg in cmd)

  first_cmd:list[str] = []
  first_out:str = ''
  status = 0
  for cmd in test_cmds:
    if dbg: errSL('\nrunning test:', quote(cmd))
    code, out = runCO(cmd)
    if code != 0:
      errSL('test failed:', quote(cmd))
      outZ(out)
      exit(1)
    if not first_cmd:
      first_cmd = cmd
      first_out = out
      outZ(first_out)
    elif out != first_out:
      errL('test outputs differ:')
      errSL('-$', quote(first_cmd))
      errSL('+$', quote(cmd))
      errZ(*ndiff(first_out.splitlines(keepends=True), out.splitlines(keepends=True)))
      status = 1
  exit(status)


def match_bytes(nfa:NFA, fat_dfa:DFA, min_dfa:DFA, text:str, text_bytes:bytes) -> None:
  '''
  Test `nfa`, `fat_dfa`, and `min_dfa` against each other by attempting to match `string`.
  This is tricky because each is subtly different:
  * NFA does not have any transitions to `invalid`.
  * fat DFA does not disambiguate between multiple match states.
  Therefore the minimized DFA is most correct,
  but for now it seems worthwhile to keep the ability to check them against each other.
  '''
  nfa_matches = nfa.match(text_bytes)
  fat_dfa_matches = fat_dfa.match(text_bytes)
  if nfa_matches != fat_dfa_matches:
    if not (nfa_matches == frozenset() and fat_dfa_matches == frozenset({'invalid'})): # allow this special case.
      exit(f'match: {text!r}; inconsistent matches: NFA: {nfa_matches}; fat DFA: {fat_dfa_matches}.')
  min_dfa_matches = min_dfa.match(text_bytes)
  if not (fat_dfa_matches >= min_dfa_matches):
    exit(f'match: {text!r}; inconsistent matches: fat DFA: {fat_dfa_matches}; min DFA: {min_dfa_matches}.')
  assert len(min_dfa_matches) <= 1, min_dfa_matches
  if min_dfa_matches:
    outL(f'match: {text!r} -> {first_el(min_dfa_matches)}')
  else:
    outL(f'match: {text!r} -- <none>')


ext_langs = {
  '.dot' : 'dot',
  '.py' : 'python',
  '.re.py' : 'python-re',
  '.swift' : 'swift',
}

supported_langs = {'dot', 'python', 'python-re', 'swift', 'vscode'}
test_langs = {'python', 'swift'}


if __name__ == "__main__": main()
