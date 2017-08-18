#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser, Namespace
from collections import defaultdict
from itertools import chain, count
from typing import *

from pithy.collection import freeze
from pithy.dict_utils import dict_put
from pithy.fs import path_ext
from pithy.io import errL, errSL, errLL, errZ, outL, outZ
from pithy.string_utils import pluralize
from pithy.task import runCO

from legs.defs import Mode, ModeTransitions
from legs.parse import parse_legs
from legs.dfa import DFA, DfaTransitions, minimizeDFA
from legs.nfa import NFA, genDFA
from legs.rules import NfaMutableTransitions, Rule
from legs.swift import output_swift
from legs.python import output_python3


def main() -> None:
  parser = ArgumentParser(prog='legs')
  parser.add_argument('path', nargs='?', help='Path to the .legs file.')
  parser.add_argument('-patterns', nargs='+', help='Specify legs patterns for quick testing.')
  parser.add_argument('-dbg', action='store_true', help='Verbose debug printing.')
  parser.add_argument('-match', nargs='+', help='Attempt to lex each argument string.')
  parser.add_argument('-mode', default=None, help='Mode with which to lex the arguments to `-match`.')
  parser.add_argument('-output', default=None, help='Path to output generated source.')
  parser.add_argument('-language', default=None, help='Generated source target language.')
  parser.add_argument('-stats', action='store_true', help='Print statistics about the generated automata.')
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
  if args.match and args.language: exit('`-match` and `-language` are mutually exclusive.')
  if args.match and args.test: exit('`-match` and `-test` are mutually exclusive.')

  if args.test and not args.output: exit('`-test` requires `-output`.')

  langs: Set[str]
  if args.language:
    if args.language not in supported_langs:
      exit(f'unknown language {args.language!r}; supported languages are: {sorted(supported_langs)}.')
    langs = {args.language}
  elif args.test:
    langs = set(supported_langs)
    langs = {'swift'} # TEMPORARY.
  elif args.output:
    ext = path_ext(args.output)
    try: langs = {ext_langs[ext]}
    except KeyError:
      exit(f'unsupported output extension {ext!r}; supported extensions are: {sorted(ext_langs)}.')
  else:
    langs = set()

  if (args.path is None) and args.patterns:
    path = '<patterns>'
    src = '\n'.join(args.patterns)
  elif (args.path is not None) and not args.patterns:
    path = args.path
    try: src = open(path).read()
    except FileNotFoundError:
      exit(f'legs error: no such rule file: {path!r}')
  else:
    exit('`must specify either `path` or `-patterns`.')

  license, patterns, mode_rule_names, transitions = parse_legs(path, src)

  if dbg:
    errSL('\nPatterns:')
    for name, rule in patterns.items():
      rule.describe(name=name)
    errL()

  requires_dfa = args.match or langs.intersection(dfa_langs)

  mode_dfa_pairs: List[Tuple[str, DFA]] = []
  for mode, rule_names in sorted(mode_rule_names.items()):
    if args.match and mode != match_mode: continue
    named_rules = sorted((name, patterns[name]) for name in rule_names)
    nfa = genNFA(mode, named_rules=named_rules)
    if dbg: nfa.describe(f'{mode} NFA')
    if dbg or args.stats: nfa.describe_stats(f'{mode} NFA Stats')
    msgs = nfa.validate()
    if msgs:
      errLL(*msgs)
      exit(1)

    # Always generate the fat DFA, which checks for ambiguous rules.
    fat_dfa = genDFA(nfa)
    if dbg: fat_dfa.describe('Fat DFA')
    if dbg or args.stats: fat_dfa.describe_stats('Fat DFA Stats')

    if not requires_dfa: continue # Skip expensive minimization step.

    min_dfa = minimizeDFA(fat_dfa)
    if dbg: min_dfa.describe('Min DFA')
    if dbg or args.stats: min_dfa.describe_stats('Min DFA Stats')
    mode_dfa_pairs.append((mode, min_dfa))

    if args.match and mode == match_mode:
      for string in args.match:
        match_string(nfa, fat_dfa, min_dfa, string)
      exit()

    if dbg: errL('----')

    post_matches = len(min_dfa.postMatchNodes)
    if post_matches:
      errL(f'note: `{mode}`: minimized DFA contains ', pluralize(post_matches, "post-match node"), '.')

  if args.match: exit(f'bad mode: {match_mode!r}')

  rule_descs = { name : rule.literalDesc or name for name, rule in patterns.items() }
  rule_descs['invalid'] = 'invalid'
  rule_descs['incomplete'] = 'incomplete'

  test_cmds: List[List[str]] = []
  if 'python3' in langs:
    path = args.output + ('.py' if args.test else '')
    output_python3(path, patterns=patterns, mode_rule_names=mode_rule_names, transitions=transitions,
      rule_descs=rule_descs, license=license, args=args)
    if args.test: test_cmds.append(['python3', path] + args.test)

  if not requires_dfa: return

  dfa, modes, node_modes = combine_dfas(mode_dfa_pairs, mode_rule_names)
  if dbg: dfa.describe('Combined DFA')

  if 'swift' in langs:
    path = args.output + ('.swift' if args.test else '')
    output_swift(path, modes=modes, mode_transitions=transitions, dfa=dfa, node_modes=node_modes,
      rule_descs=rule_descs, license=license, args=args)
    if args.test: test_cmds.append(['swift', path] + args.test)

  if args.test:
    # For each language, run against the specified match arguments, and capture output.
    # If all of the tests have identical output, then print it; otherwise print each output.
    from difflib import ndiff
    from shlex import quote as sh_quote
    def quote(cmd: List[str]) -> str: return ' '.join(sh_quote(arg) for arg in cmd)
    first_out = None
    status = 0
    for cmd in test_cmds:
      if args.dbg: errL('\nrunning test:', quote(cmd))
      code, out = runCO(cmd)
      if code != 0:
        errSL('test failed:', quote(cmd))
        outZ(out)
        exit(1)
      if first_out is None:
        first_out = out
        outZ(first_out)
      elif out != first_out:
        errL('test outputs differ:')
        errSL('-$', quote(test_cmds[0]))
        errSL('+$', quote(cmd))
        errLL(*ndiff(first_out.split('\n'), out.split('\n')))
        status = 1
    exit(status)


def match_string(nfa: NFA, fat_dfa: DFA, min_dfa: DFA, string: str) -> None:
  'Test `nfa`, `fat_dfa`, and `min_dfa` against each other by attempting to match `string`.'
  nfa_matches = nfa.match(string)
  if len(nfa_matches) > 1:
    exit(f'match: {string!r}: NFA matched multiple rules: {", ".join(sorted(nfa_matches))}.')
  nfa_match = list(nfa_matches)[0] if nfa_matches else None
  fat_dfa_match = fat_dfa.match(string)
  if fat_dfa_match != nfa_match:
    exit(f'match: {string!r} inconsistent match: NFA: {nfa_match}; fat DFA: {fat_dfa_match}.')
  min_dfa_match = min_dfa.match(string)
  if min_dfa_match != nfa_match:
    exit(f'match: {string!r} inconsistent match: NFA: {nfa_match}; min DFA: {min_dfa_match}.')
  if nfa_match:
    outL(f'match: {string!r} -> {nfa_match}')
  else:
    outL(f'match: {string!r} -- incomplete')


def genNFA(mode: str, named_rules: List[Tuple[str, Rule]]) -> NFA:
  '''
  Generate an NFA from a set of rules.
  The NFA can be used to match against an argument string,
  but cannot produce a token stream directly.
  The `invalid` node is unreachable, and reserved for later use by the derived DFA.
  '''

  indexer = iter(count())
  def mk_node() -> int: return next(indexer)

  start = mk_node() # always 0; see genDFA.
  invalid = mk_node() # always 1; see genDFA.

  matchNodeNames: Dict[int, str] = { invalid: 'invalid' }

  transitions: NfaMutableTransitions = defaultdict(lambda: defaultdict(set))
  for name, rule in named_rules:
    matchNode = mk_node()
    rule.genNFA(mk_node, transitions, start, matchNode)
    dict_put(matchNodeNames, matchNode, name) # type: ignore # mypy bug?
  literalRules = { name for name, rule in named_rules if rule.isLiteral }
  return NFA(transitions=freeze(transitions), matchNodeNames=matchNodeNames, literalRules=literalRules)


def combine_dfas(mode_dfa_pairs: Iterable[Tuple[str, DFA]], mode_rule_names: Dict[str, List[str]]) \
 -> Tuple[DFA, List[Mode], Dict[int, Mode]]:
  indexer = iter(count())
  def mk_node() -> int: return next(indexer)
  transitions: DfaTransitions = {}
  matchNodeNames: Dict[int, str] = {}
  literalRules: Set[str] = set()
  modes: List[Mode] = []
  node_modes: Dict[int, Mode] = {}
  for mode_name, dfa in sorted(mode_dfa_pairs, key=lambda p: '' if p[0] == 'main' else p[0]):
    remap = { node : mk_node() for node in sorted(dfa.allNodes) } # preserves existing order of dfa nodes.
    mode = Mode(name=mode_name, start=remap[0], invalid=remap[1])
    modes.append(mode)
    node_modes.update((node, mode) for node in remap.values())
    def remap_trans_dict(d: Dict[int, int]): return { c : remap[dst] for c, dst in d.items() }
    transitions.update((remap[src], remap_trans_dict(d)) for src, d in sorted(dfa.transitions.items()))
    matchNodeNames.update((remap[node], name) for node, name in sorted(dfa.matchNodeNames.items()))
    literalRules.update(dfa.literalRules)
  return (DFA(transitions=transitions, matchNodeNames=matchNodeNames, literalRules=literalRules), modes, node_modes)


ext_langs = {
  '.swift' : 'swift',
  '.py' : 'python3',
}

supported_langs = {'python3', 'swift'}

dfa_langs = {'swift'} # languages which require the combined dfa.

if __name__ == "__main__": main()
