#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser, Namespace
from collections import defaultdict
from itertools import chain, count
from typing import DefaultDict, Dict, FrozenSet, Iterable, List, Set, Tuple

from pithy.collection import freeze
from pithy.dict import dict_put
from pithy.fs import path_ext, path_stem
from pithy.io import errL, errLL, errSL, errZ, outL, outZ
from pithy.iterable import first_el
from pithy.string import pluralize

from ..defs import Mode, ModeTransitions
from ..dfa import DFA, DfaTransitions, minimize_dfa
from ..nfa import NFA, gen_dfa
from ..parse import parse_legs
from ..patterns import NfaMutableTransitions, Pattern
from ..python import output_python3
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

  if args.test and not args.output: exit('`-test` requires `-output`.')

  langs:Set[str]
  if args.langs:
    for lang in args.langs:
      if lang not in supported_langs:
        exit(f'unknown language {lang!r}; supported languages are: {sorted(supported_langs)}.')
    langs = args.langs
  elif args.test:
    langs = test_langs
  elif args.output:
    ext = path_ext(args.output)
    try: langs = {ext_langs[ext]}
    except KeyError:
      exit(f'unsupported output language extension {ext!r}; supported extensions are: {sorted(ext_langs)}.')
  else:
    langs = set()

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

  license, patterns, mode_pattern_names, transitions = parse_legs(path, src)

  if dbg:
    errSL('\nPatterns:')
    for name, pattern in patterns.items():
      pattern.describe(name=name)
    errL()

  mode_dfa_pairs:List[Tuple[str, DFA]] = []
  for mode, pattern_names in sorted(mode_pattern_names.items()):
    if args.match and mode != match_mode: continue

    named_patterns = sorted((name, patterns[name]) for name in pattern_names)
    nfa = gen_nfa(mode, named_patterns=named_patterns)
    if dbg: nfa.describe(f'{mode}: NFA')
    if dbg or args.stats: nfa.describe_stats(f'{mode} NFA Stats')
    msgs = nfa.validate()
    if msgs:
      errLL(*msgs)
      exit(1)

    fat_dfa = gen_dfa(nfa)
    if dbg: fat_dfa.describe(f'{mode}: Fat DFA')
    if dbg or args.stats: fat_dfa.describe_stats('Fat DFA Stats')

    min_dfa = minimize_dfa(fat_dfa)
    if dbg: min_dfa.describe(f'{mode}: Min DFA')
    if dbg or args.stats: min_dfa.describe_stats('Min DFA Stats')
    mode_dfa_pairs.append((mode, min_dfa))

    if args.match and mode == match_mode:
      for string in args.match:
        match_string(nfa, fat_dfa, min_dfa, string)
      exit()

    if dbg: errL('----')

    post_matches = len(min_dfa.post_match_nodes)
    if post_matches:
      errL(f'note: `{mode}`: minimized DFA contains ', pluralize(post_matches, "post-match node"), '.')

  if args.match: exit(f'bad mode: {match_mode!r}')

  pattern_descs = { name : pattern.literal_desc or name for name, pattern in patterns.items() }
  pattern_descs['invalid'] = 'invalid'
  pattern_descs['incomplete'] = 'incomplete'

  dfa, modes, node_modes = combine_dfas(mode_dfa_pairs, mode_pattern_names)
  if dbg: dfa.describe('Combined DFA')

  test_cmds:List[List[str]] = []

  mode_transitions:DefaultDict[int, Dict[str, Tuple[int, str]]] = defaultdict(dict)
  # mode_transitions maps parent_start : (parent_kind : (child_start, child_kind)).
  for (parent_mode_name, parent_kind), (child_mode_name, child_kind) in transitions.items():
    parent_start = modes[parent_mode_name].start
    child_start = modes[child_mode_name].start
    mode_transitions[parent_start][parent_kind] = (child_start, child_kind)

  if 'python3' in langs:
    path = path_for_output(args.output, '.py')
    output_python3(path, mode_transitions=mode_transitions, dfa=dfa,
      pattern_descs=pattern_descs, license=license, args=args)
    if args.test: test_cmds.append(['python3', path] + args.test)

  if 'swift' in langs:
    path = path_for_output(args.output, '.swift')
    output_swift(path, mode_transitions=mode_transitions, dfa=dfa, node_modes=node_modes,
      pattern_descs=pattern_descs, license=license, args=args)
    if args.test: test_cmds.append(['swift', path] + args.test)

  if 'vscode' in langs:
    path = path_for_output(args.output, '.json')
    output_vscode(path, patterns=patterns, mode_pattern_names=mode_pattern_names,
      pattern_descs=pattern_descs, license=license, args=args)

  if args.test:
    run_tests(test_cmds, dbg=args.dbg)


def path_for_output(output:str, ext:str) -> str:
  return path_stem(output) + ext


def run_tests(test_cmds:List[List[str]], dbg:bool) -> None:
  # For each language, run against the specified match arguments, and capture output.
  # Print the output from the first test, and then the diff for each subsequent output that differs.
  from difflib import ndiff
  from shlex import quote as sh_quote
  from pithy.task import runCO

  def quote(cmd:List[str]) -> str: return ' '.join(sh_quote(arg) for arg in cmd)

  first_cmd = None
  first_out = None
  status = 0
  for cmd in test_cmds:
    if dbg: errL('\nrunning test:', quote(cmd))
    code, out = runCO(cmd)
    if code != 0:
      errSL('test failed:', quote(cmd))
      outZ(out)
      exit(1)
    if first_cmd is None:
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


def match_string(nfa:NFA, fat_dfa:DFA, min_dfa:DFA, string: str) -> None:
  '''
  Test `nfa`, `fat_dfa`, and `min_dfa` against each other by attempting to match `string`.
  This tricky because each is subtly different:
  * NFA does not have any transitions to `invalid`.
  * fat DFA does not disambiguate between multiple match states.
  Therefore the minimized DFA is most correct,
  but for now it seems worthwhile to keep the ability to check them against each other.
  '''
  nfa_matches = nfa.match(string)
  fat_dfa_matches = fat_dfa.match(string)
  if nfa_matches != fat_dfa_matches:
    if not (nfa_matches == frozenset() and fat_dfa_matches == frozenset({'invalid'})): # allow this special case.
      exit(f'match: {string!r}; inconsistent matches: NFA: {nfa_matches}; fat DFA: {fat_dfa_matches}.')
  min_dfa_matches = min_dfa.match(string)
  if not (fat_dfa_matches >= min_dfa_matches):
    exit(f'match: {string!r}; inconsistent matches: fat DFA: {fat_dfa_matches}; min DFA: {min_dfa_matches}.')
  assert len(min_dfa_matches) <= 1, min_dfa_matches
  if min_dfa_matches:
    outL(f'match: {string!r} -> {first_el(min_dfa_matches)}')
  else:
    outL(f'match: {string!r} -- <none>')


def gen_nfa(mode:str, named_patterns:List[Tuple[str, Pattern]]) -> NFA:
  '''
  Generate an NFA from a set of patterns.
  The NFA can be used to match against an argument string,
  but cannot produce a token stream directly.
  The `invalid` node is unreachable, and reserved for later use by the derived DFA.
  '''

  indexer = iter(count())
  def mk_node() -> int: return next(indexer)

  start = mk_node() # always 0; see gen_dfa.
  invalid = mk_node() # always 1; see gen_dfa.

  match_node_names:Dict[int, str] = { invalid: 'invalid' }

  transitions:NfaMutableTransitions = defaultdict(lambda: defaultdict(set))
  for name, pattern in named_patterns:
    match_node = mk_node()
    pattern.gen_nfa(mk_node, transitions, start, match_node)
    dict_put(match_node_names, match_node, name)
  lit_patterns = { name for name, pattern in named_patterns if pattern.is_literal }
  return NFA(transitions=freeze(transitions), match_node_names=match_node_names, lit_patterns=lit_patterns)


def combine_dfas(mode_dfa_pairs:Iterable[Tuple[str, DFA]], mode_pattern_names:Dict[str, List[str]]) \
 -> Tuple[DFA, Dict[str, Mode], Dict[int, Mode]]:
  indexer = iter(count())
  def mk_node() -> int: return next(indexer)
  transitions:DfaTransitions = {}
  match_node_name_sets:Dict[int, FrozenSet[str]] = {}
  lit_patterns:Set[str] = set()
  modes:Dict[str, Mode] = {}
  node_modes:Dict[int, Mode] = {}
  for mode_name, dfa in sorted(mode_dfa_pairs, key=lambda p: '' if p[0] == 'main' else p[0]):
    remap = { node : mk_node() for node in sorted(dfa.all_nodes) } # preserves existing order of dfa nodes.
    mode = Mode(name=mode_name, start=remap[0], invalid=remap[1])
    modes[mode_name] = mode
    node_modes.update((node, mode) for node in remap.values())
    def remap_trans_dict(d:Dict[int, int]): return { c : remap[dst] for c, dst in d.items() }
    transitions.update((remap[src], remap_trans_dict(d)) for src, d in sorted(dfa.transitions.items()))
    match_node_name_sets.update((remap[node], names) for node, names in sorted(dfa.match_node_name_sets.items()))
    lit_patterns.update(dfa.lit_patterns)
  return (DFA(transitions=transitions, match_node_name_sets=match_node_name_sets, lit_patterns=lit_patterns), modes, node_modes)


ext_langs = {
  '.py' : 'python3',
  '.swift' : 'swift',
}

supported_langs = {'python3', 'swift', 'vscode'}
test_langs = {'python3', 'swift'}


if __name__ == "__main__": main()
