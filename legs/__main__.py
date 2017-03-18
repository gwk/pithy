#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from collections import defaultdict
from itertools import chain, count

from pithy.collection import freeze
from pithy.dict_utils import dict_put
from pithy.fs import path_ext, path_name_stem
from pithy.immutable import Immutable
from pithy.io import errL, errSL, errLL, outL
from pithy.iterable import fan_by_key_fn, group_by_heads, OnHeadless
from pithy.string_utils import pluralize

from legs.parse import parse_legs
from legs.automata import NFA, DFA, empty_symbol, genDFA, minimizeDFA
from legs.swift import output_swift


def main():
  parser = ArgumentParser(prog='legs')
  parser.add_argument('rules_path', nargs='?')
  parser.add_argument('-patterns', nargs='+')
  parser.add_argument('-dbg', action='store_true')
  parser.add_argument('-match', nargs='+')
  parser.add_argument('-mode', default=None)
  parser.add_argument('-output')
  parser.add_argument('-language', default=None)
  parser.add_argument('-stats', action='store_true')
  parser.add_argument('-test', action='store_true')
  parser.add_argument('-type-prefix', default='')
  parser.add_argument('-license', default='NO LICENSE SPECIFIED')
  args = parser.parse_args()
  dbg = args.dbg

  is_match_specified = args.match is not None
  is_mode_specified = args.mode is not None
  target_mode = args.mode or 'main'
  if not is_match_specified and is_mode_specified:
    exit('`-mode` option only valid with `-match`.')

  if args.language is not None:
    ext = '.' + args.languageext
    if ext not in supported_exts:
      exit(f'unknown language {args.language!r}; supported extensions are: {supported_exts}.')
  elif args.output:
    ext = path_ext(args.output)
    if ext not in supported_exts:
      exit(f'unknown output extension {ext!r}; supported extensions are: {supported_exts}.')
  else:
    ext = None

  if (args.rules_path is None) and args.patterns:
    path = '<patterns>'
    lines = args.patterns
  elif (args.rules_path is not None) and not args.patterns:
    path = args.rules_path
    try: lines = open(path)
    except FileNotFoundError:
      exit(f'legs error: no such rule file: {path!r}')
  else:
    exit('`must specify either `rules_path` or `-pattern`.')
  mode_named_rules, mode_transitions = parse_legs(path, lines)

  mode_dfa_pairs = []
  for mode, named_rules in sorted(mode_named_rules.items()):
    if is_match_specified and mode != target_mode:
      continue
    if dbg:
      errSL('\nmode:', mode)
      for name, rule in named_rules:
        rule.describe(name=name)
      errL()
    nfa = genNFA(mode, named_rules)
    if dbg: nfa.describe()
    if dbg or args.stats: nfa.describe_stats('NFA Stats')

    msgs = nfa.validate()
    if msgs:
      errLL(*msgs)
      exit(1)

    fat_dfa = genDFA(nfa)
    if dbg: fat_dfa.describe('Fat DFA')
    if dbg or args.stats: fat_dfa.describe_stats('Fat DFA Stats')

    min_dfa = minimizeDFA(fat_dfa)
    if dbg: min_dfa.describe('Min DFA')
    if dbg or args.stats: min_dfa.describe_stats('Min DFA Stats')
    mode_dfa_pairs.append((mode, min_dfa))

    if is_match_specified and mode == target_mode:
      for string in args.match:
        match_string(nfa, fat_dfa, min_dfa, string)
      exit()

    if dbg: errL('----')

    post_matches = len(min_dfa.postMatchNodes)
    if post_matches:
      errSL(f'note: `{mode}`: minimized DFA contains', pluralize(post_matches, "post-match node"))

  if is_match_specified: exit(f'bad mode: {target_mode!r}')

  if dbg and mode_transitions:
    errSL('\nmode transitions:')
    for a, b in mode_transitions:
      errSL('  %', a, b)

  dfa, modes, node_modes = combine_dfas(mode_dfa_pairs)
  if ext:
    output(dfa=dfa, modes=modes, node_modes=node_modes, mode_transitions=mode_transitions, ext=ext, args=args)


supported_exts = ['.swift']


def match_string(nfa, fat_dfa, min_dfa, string):
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


def genNFA(mode, named_rules):
  '''
  Generate an NFA from a set of rules.
  The NFA can be used to match against an argument string,
  but cannot produce a token stream directly.
  The `invalid` node is unreachable, and reserved for later use by the derived DFA.
  '''

  indexer = iter(count())
  def mk_node(): return next(indexer)

  start = mk_node() # always 0; see genDFA.
  invalid = mk_node() # always 1; see genDFA.

  matchNodeNames = { invalid: ('invalid' if (mode == 'main') else mode + '_invalid') }

  transitions = defaultdict(lambda: defaultdict(set))
  for name, rule in sorted(named_rules):
    matchNode = mk_node()
    rule.genNFA(mk_node, transitions, start, matchNode)
    dict_put(matchNodeNames, matchNode, name)
  literalRules = { name : rule.literalPattern for name, rule in named_rules if rule.isLiteral }
  return NFA(transitions=freeze(transitions), matchNodeNames=matchNodeNames, literalRules=literalRules)


def combine_dfas(mode_dfa_pairs):
  indexer = iter(count())
  def mk_node(): return next(indexer)
  transitions = {}
  matchNodeNames = {}
  literalRules = {}
  modes = []
  node_modes = {}
  for mode_name, dfa in sorted(mode_dfa_pairs, key=lambda p: '' if p[0] == 'main' else p[0]):
    remap = { node : mk_node() for node in sorted(dfa.allNodes) } # preserves existing order of dfa nodes.
    incomplete_name = 'incomplete' if (mode_name == 'main') else mode_name + '_incomplete'
    mode = Immutable(name=mode_name, start=remap[0], invalid=remap[1],
      invalid_name=dfa.matchNodeNames[1], incomplete_name=incomplete_name)
    modes.append(mode)
    node_modes.update((node, mode) for node in remap.values())
    def remap_trans_dict(d): return { c : remap[dst] for c, dst in d.items() }
    transitions.update((remap[src], remap_trans_dict(d)) for src, d in sorted(dfa.transitions.items()))
    matchNodeNames.update((remap[node], name) for node, name in sorted(dfa.matchNodeNames.items()))
    literalRules.update(dfa.literalRules)
  return (DFA(transitions=transitions, matchNodeNames=matchNodeNames, literalRules=literalRules), modes, node_modes)


def output(dfa, modes, node_modes, mode_transitions, ext, args):

  if ext not in supported_exts:
    exit(f'output path has unknown extension {ext!r}; supported extensions are: {", ".join(supported_exts)}.')
  if ext == '.swift':
    output_swift(dfa=dfa, modes=modes, node_modes=node_modes, mode_transitions=mode_transitions, args=args)
  else:
    raise Exception('output type not implemented: {}'.format(ext))


if __name__ == "__main__": main()
