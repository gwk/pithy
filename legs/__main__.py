#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# NFA/DFA implementation derived from http://www-bcf.usc.edu/~breichar/teaching/2011cs360/NFAtoDFA.py.

import re

from argparse import ArgumentParser
from collections import defaultdict
from itertools import chain, count

from pithy.collection_utils import freeze
from pithy.dict_utils import dict_filter_map, dict_put
from pithy.fs import path_ext, path_name_stem
from pithy.immutable import Immutable
from pithy.io import errF, errFL, errL, errSL, errLL, failF, failS, outFL
from pithy.seq import fan_seq_by_key, fan_seq_by_pred, seq_first
from pithy.string_utils import prefix_nonempty
from pithy.type_util import is_str

from legs.swift import output_swift


def main():
  parser = ArgumentParser(prog='legs')
  parser.add_argument('rules_path', nargs='?')
  parser.add_argument('-patterns', nargs='+')
  parser.add_argument('-dbg', action='store_true')
  parser.add_argument('-match', nargs='+')
  parser.add_argument('-mode', default=None)
  parser.add_argument('-output')
  parser.add_argument('-test', action='store_true')
  parser.add_argument('-type-prefix', default='')
  parser.add_argument('-license', default='NO LICENSE SPECIFIED')
  args = parser.parse_args()
  dbg = args.dbg

  is_match_specified = args.match is not None
  is_mode_specified = args.mode is not None
  target_mode = args.mode or 'main'
  if not is_match_specified and is_mode_specified:
    failF('`-mode` option only valid with `-match`.')

  if (args.rules_path is None) and args.patterns:
    path = '<patterns>'
    lines = args.patterns
  elif (args.rules_path is not None) and not args.patterns:
    path = args.rules_path
    try: lines = open(path)
    except FileNotFoundError:
      failF('legs error: no such rule file: {!r}', path)
  else:
    failF('`must specify either `rules_path` or `-pattern`.')
  mode_rules, mode_transitions = compile_rules(path, lines)

  mode_dfa_pairs = []
  for mode, rules in sorted(mode_rules.items()):
    if is_match_specified and mode != target_mode:
      continue
    if dbg:
      errSL('\nmode:', mode)
      for rule in rules:
        rule.describe()
      errL()
    nfa = genNFA(mode, rules)
    if dbg: nfa.describe()

    msgs = nfa.validate()
    if msgs:
      errLL(*msgs)
      exit(1)

    fat_dfa = genDFA(nfa)
    if dbg: fat_dfa.describe('Fat DFA')

    min_dfa = minimizeDFA(fat_dfa)
    if dbg: min_dfa.describe('Min DFA')
    mode_dfa_pairs.append((mode, min_dfa))

    if is_match_specified and mode == target_mode:
      for string in args.match:
        match_string(nfa, fat_dfa, min_dfa, string)
      exit()

    if dbg: errL('----')

    postMatchNodes = min_dfa.postMatchNodes
    if postMatchNodes:
      if not dbg: min_dfa.describe('Minimized DFA')
      failS('error: minimized DFA contains post-match nodes:', *sorted(postMatchNodes))

  if is_match_specified: failF('bad mode: {!r}', target_mode)

  if dbg and mode_transitions:
    errSL('\nmode transitions:')
    for t in mode_transitions:
      errL(t)

  dfa, modes, node_modes = combine_dfas(mode_dfa_pairs)
  if args.output is not None:
    output(dfa=dfa, modes=modes, node_modes=node_modes, mode_transitions=mode_transitions,
      rules_path=args.rules_path, path=args.output, test=args.test, type_prefix=args.type_prefix, license=args.license)


def match_string(nfa, fat_dfa, min_dfa, string):
  'Test `nfa`, `fat_dfa`, and `min_dfa` against each other by attempting to match `string`.'
  nfa_matches = nfa.match(string)
  if len(nfa_matches) > 1:
    failF('match: {!r}: NFA matched multiple rules: {}.', string, ', '.join(sorted(nfa_matches)))
  nfa_match = list(nfa_matches)[0] if nfa_matches else None
  fat_dfa_match = fat_dfa.match(string)
  if fat_dfa_match != nfa_match:
    failF('match: {!r} inconsistent match: NFA: {}; fat DFA: {}.', string, nfa_match, fat_dfa_match)
  min_dfa_match = min_dfa.match(string)
  if min_dfa_match != nfa_match:
    failF('match: {!r} inconsistent match: NFA: {}; min DFA: {}.', string, nfa_match, min_dfa_match)
  outFL('match: {!r} {} {}', string, *(('->', nfa_match) if nfa_match else ('--', 'invalid')))


rule_re = re.compile(r'''(?x)
\s* (?: # ignore leading space.
| (?P<comment> \# .*)
| (?P<l_name> [\w.]+ ) \s+ -> \s+ (?P<r_name> [^\#\s]+ ) # mode transition.
| (?P<name> [\w.]+ ) (?P<esc>\s+\\.)? \s* : \s* (?P<named_pattern> .*)
| (?P<unnamed_pattern> .+) # must come last due to wildcard.
) \s* # ignore trailing space.
''')

def compile_rules(path, lines):
  'Compile the rules given in `lines`.'
  rules = []
  mode_transitions = {}
  rule_names = set()
  for line_num, line in enumerate(lines):
    line = line.rstrip() # always strip newline so that missing final newline is consistent.
    if not line: continue
    line_info = (path, line_num, line)
    m = rule_re.fullmatch(line)
    if m.group('comment'): continue
    if m.group('l_name'): # mode transition.
      (src_pair, dst_pair) = parse_mode_transition(line_info, m)
      if src_pair in mode_transitions:
        fail_parse((line_info, 0), 'duplicate transition parent name: {!r}', src_pair[1])
      mode_transitions[src_pair] = dst_pair
    else:
      rule = compile_rule(line_info, m)
      if rule.name in rule_names:
        fail_parse((line_info, 0), 'duplicate rule name: {!r}', rule.name)
      rule_names.add(rule.name)
      rules.append(rule)
  return fan_seq_by_key(rules, lambda rule: rule.mode), mode_transitions


def parse_mode_transition(line_info, match):
  return (
    parse_mode_and_name(line_info, match, 'l_name'),
    parse_mode_and_name(line_info, match, 'r_name'))

def parse_mode_and_name(line_info, match, key):
  name = match.group(key)
  match = re.match(r'[a-z]\w*(\.\w+)?', name)
  end = match.end() if match else 0
  if end < len(name):
    fail_parse((line_info, end), 'invalid name.')
  return (mode_for_name(name), simplify_name(name))


def simplify_name(name):
  return name.replace('.', '_')


def mode_for_name(name):
  match = re.match(r'([^.]+)\.', name)
  return match.group(1) if match else 'main'


def compile_rule(line_info, match):
  esc_char = '\\' # default.
  name = match.group('name')
  if name: # name is specified explicitly.
    esc = match.group('esc')
    if esc: # custom escape char.
      esc_char = esc[-1] # capture group begins with spaces and backslash.
    key = 'named_pattern'
  else:
    key = 'unnamed_pattern'
  pattern = match.group(key)
  start_col = match.start(key)
  if not name: # no name; derive a name from the pattern; convenient for keyword tokens and testing.
    name = re.sub('\W+', '_', pattern.strip())
    if name[0].isdigit():
      name = '_' + name
  if name == 'invalid':
    fail_parse((line_info, 0), 'rule name is reserved: {!r}.', name)
  return parse_rule_pattern(line_info=line_info, name=name, pattern=pattern, start_col=start_col, esc_char=esc_char)


def parse_rule_pattern(line_info, name, pattern, start_col, esc_char):
  'Parse a single pattern and return a Rule object.'
  parser_stack = [PatternParser((line_info, start_col))]
  # stack of parsers, one for each open nesting syntactic element: root, '(…)', or '[…]'.
  escape = False
  end_col = len(pattern)
  for col, c in enumerate(pattern, start_col):
    pos = (line_info, col)
    parser = parser_stack[-1]
    if escape:
      escape = False
      try: escaped_chars = escape_char_sets[c]
      except KeyError: fail_parse(pos, 'invalid escaped character: {!r}', c)
      else: parser.parse_escaped(pos, escaped_chars)
    elif c == esc_char:
      escape = True
    elif c == '#':
      end_col = col
      break
    elif c.isspace():
      continue
    elif not c.isprintable():
      fail_parse(pos, 'invalid non-printing character: {!r}'. c)
    elif c == parser.terminator:
      parser_stack.pop()
      parent = parser_stack[-1]
      parent.receive(parser.finish())
    else:
      child = parser.parse(pos, c)
      if child:
        parser_stack.append(child)
  if escape:
    fail_parse(pos, 'dangling escape: {!r}', esc_char)
  parser = parser_stack.pop()
  if parser_stack:
    fail_parse((line_info, end_col), 'expected terminator: {!r}', parser.terminator)
  rule = parser.finish()
  rule.name = simplify_name(name)
  rule.mode = mode_for_name(name)
  rule.pattern = pattern[start_col:end_col].strip()
  return rule


def fail_parse(pos, fmt, *items):
  'Print a formatted parsing failure to std err and exit.'
  (line_info, col) = pos
  (path, line_num, line_text) = line_info
  failF('{}:{}:{}: ' + fmt + '\n{}\n{}^', path, line_num + 1, col + 1, *items, line_text, ' ' * col)


def char_intervals(*intervals):
  "Return a `str` object containing the specified range of characters denoted by each character pair."
  points = frozenset().union(*(range(ord(i), ord(j) + 1) for i, j in intervals))
  return ''.join(chr(p) for p in sorted(points))

escape_char_sets = {
  'd': char_intervals('09'),
  'l': char_intervals('az', 'AZ'), # nonstandard 'letter' escape.
  'w': char_intervals('az', 'AZ', '09'),
  'n': '\n',
  't': '\t',
  '_': ' ', # nonstandard space escape.
}
escape_char_sets.update((c, c) for c in '\\|?*+()[]#')

#for k, v in escape_char_sets.items():
#  errFL('{}: {!r}', k, v)


class PatternParser:

  def __init__(self, pos, terminator=None):
    self.pos = pos
    self.terminator = terminator
    self.choices = []
    self.seq = []
    self.seq_pos = pos

  def parse(self, pos, c):
    if c == '(':
      return PatternParser(pos, terminator=')')
    elif c == '[':
      return CharsetParser(pos)
    elif c == '|':
      self.flush_seq(pos)
    elif c == '?': self.quantity(pos, c, Opt)
    elif c == '*': self.quantity(pos, c, Star)
    elif c == '+': self.quantity(pos, c, Plus)
    else:
      self.seq.append(Charset(pos, chars=c))

  def parse_escaped(self, pos, chars):
    self.seq.append(Charset(pos, chars=chars))

  def finish(self):
    self.flush_seq(pos=None)
    choices = self.choices
    return choices[0] if len(choices) == 1 else Choice(self.pos, subs=tuple(choices))

  def flush_seq(self, pos):
    seq = self.seq
    if not seq: fail_parse(self.seq_pos, 'empty sequence.')
    rule = seq[0] if len(seq) == 1 else Seq(self.seq_pos, subs=tuple(seq))
    self.choices.append(rule)
    self.seq = []
    self.seq_pos = pos

  def quantity(self, pos, char, T):
    try: el = self.seq.pop()
    except IndexError: fail_parse(pos, "'{}' does not follow any pattern.", char)
    else: self.seq.append(T(pos, subs=(el,)))

  def receive(self, result):
    self.seq.append(result)


class CharsetParser():

  def __init__(self, pos):
    self.pos = pos
    self.terminator = ']'
    self.chars = set()
    self.fresh = True
    self.invert = False

  def parse(self, pos, c):
    if self.fresh:
      self.fresh = False
      if c == '^':
        self.invert = True
        return
    if self.invert and len(c.encode()) != 1:
      fail_parse(pos, 'non-ASCII character cannot be used within an inverted character set: {!r}.', c)
    if c in self.chars:
      fail_parse(pos, 'repeated character in set: {!r}.', c)
    self.chars.add(c)

  def parse_escaped(self, pos, escaped_chars):
    self.chars.update(escaped_chars)

  def finish(self):
    if self.invert:
      chars = set(chr(i) for i in range(0x80)) - self.chars
      # TODO: support non-ascii?
    else:
      chars = self.chars
    return Charset(self.pos, chars=''.join(sorted(chars)))


empty = -1

class Rule:
  def __init__(self, pos, subs=None):
    if subs is not None:
      assert isinstance(subs, tuple)
      for sub in subs: assert isinstance(sub, Rule)
    self.pos = pos
    self.subs = subs
    self.name = None
    self.mode = None
    self.pattern = None

  def describe(self, depth=0):
    (_, line_num, _), col = self.pos
    n = self.name + ' ' if self.name else ''
    errFL('{}{}{}:{}:{}:{}', '  ' * depth, n, type(self).__name__, line_num + 1, col + 1, self.inlineDescription)
    if self.subs:
      for sub in self.subs:
        sub.describe(depth + 1)

  @property
  def inlineDescription(self): return ''

  @property
  def isLiteral(self): return False

  @property
  def literalPattern(self): raise AssertionError('not a literal rule: {}'.format(self))


class Choice(Rule):

  def genNFA(self, mk_node, transitions, start, end):
    for choice in self.subs:
      choice.genNFA(mk_node, transitions, start, end)


class Seq(Rule):

  def genNFA(self, mk_node, transitions, start, end):
    subs = self.subs
    intermediates = [mk_node() for i in range(1, len(subs))]
    for sub, src, dst in zip(subs, [start] + intermediates, intermediates + [end]):
      sub.genNFA(mk_node, transitions, src, dst)

  @property
  def isLiteral(self): return all(sub.isLiteral for sub in self.subs)

  @property
  def literalPattern(self): return ''.join(sub.literalPattern for sub in self.subs)


class Quantity(Rule):
  @property
  def sub(self): return self.subs[0]


class Opt(Quantity):

  def genNFA(self, mk_node, transitions, start, end):
    transitions[start][empty].add(end)
    self.sub.genNFA(mk_node, transitions, start, end)


class Star(Quantity):

  def genNFA(self, mk_node, transitions, start, end):
    branch = mk_node()
    transitions[start][empty].add(branch)
    transitions[branch][empty].add(end)
    self.sub.genNFA(mk_node, transitions, branch, branch)


class Plus(Quantity):

  def genNFA(self, mk_node, transitions, start, end):
    pre = mk_node()
    post = mk_node()
    transitions[start][empty].add(pre)
    transitions[post][empty].add(end)
    transitions[post][empty].add(pre)
    self.sub.genNFA(mk_node, transitions, pre, post)


class Charset(Rule):

  def __init__(self, pos, chars):
    super().__init__(pos=pos)
    assert isinstance(chars, str)
    if not chars: fail_parse(pos, 'empty character set.')
    self.chars = chars

  def genNFA(self, mk_node, transitions, start, end):
    for char in self.chars:
      assert isinstance(char, str)
      bytes_ = char.encode()
      intermediates = [mk_node() for i in range(1, len(bytes_))]
      for byte, src, dst in zip(bytes_, [start] + intermediates, intermediates + [end]):
        transitions[src][byte].add(dst)

  @property
  def isLiteral(self): return len(self.chars) == 1

  @property
  def literalPattern(self): return self.chars

  @property
  def inlineDescription(self): return ' {!r}'.format(self.chars)


def genNFA(mode, rules):
  '''
  Generate an NFA.
  The NFA can be used to match against an argument string,
  but cannot produce a token stream directly.
  The 'invalid' node is always unreachable,
  and reserved for later use by the derived DFA.
  '''

  indexer = iter(count())
  def mk_node(): return next(indexer)

  start = mk_node() # always 0; see genDFA.
  invalid = mk_node() # always 1; see genDFA.

  matchNodeNames = {}
  transitions = defaultdict(lambda: defaultdict(set))
  invalid_name = 'invalid' if (mode == 'main') else mode + '_invalid'
  dict_put(matchNodeNames, invalid, invalid_name)
  for rule in sorted(rules, key=lambda rule: rule.name):
    matchNode = mk_node()
    rule.genNFA(mk_node, transitions, start, matchNode)
    assert rule.name
    dict_put(matchNodeNames, matchNode, rule.name)
  literalRules = { rule.name : rule.literalPattern for rule in rules if rule.isLiteral }
  return NFA(transitions=freeze(transitions), matchNodeNames=matchNodeNames, literalRules=literalRules)


def genDFA(nfa):
  '''
  A DFA node is equivalent to a set of NFA nodes.
  A DFA has a node for every reachable subset of nodes in the corresponding NFA.
  In the worst case, there will be an exponential increase in number of nodes.

  Each 'invalid' node is unreachable from its start node,
  but we explicitly add transitions from 'invalid' to itself,
  for all characters that are not transitions out of the 'start' state.
  This allows the generated lexer code to use switch default cases to enter the invalid states,
  and then continue consuming invalid characters until a start character is reached.

  For each state, the lexer switches on the current byte.
  If the switch defaults, it flushes the pending token (either invalid or the last match),
  and then performs the start transition as if it were at the start state.
  `invalid` is itself a match state;
  when in the invalid state, the lexer remains there until a valid character is encountered,
  at which point it emits an 'invalid' token and restarts.
  '''

  indexer = iter(count())
  def mk_node(): return next(indexer)

  nfa_states_to_dfa_nodes = defaultdict(mk_node)
  start = frozenset(nfa.advanceEmpties({0}))
  invalid = frozenset({1}) # no need to advanceEmpties as `invalid` is unreachable in the nfa.
  start_node = nfa_states_to_dfa_nodes[start]
  invalid_node = nfa_states_to_dfa_nodes[invalid]

  transitions = defaultdict(dict)
  alphabet = nfa.alphabet
  remaining = {start}
  while remaining:
    state = remaining.pop()
    node = nfa_states_to_dfa_nodes[state]
    d = transitions[node] # unlike NFA, DFA dictionary contains all valid nodes/states as keys.
    for char in alphabet:
      dst_state = frozenset(nfa.advance(state, char))
      if not dst_state: continue # do not add empty sets.
      dst_node = nfa_states_to_dfa_nodes[dst_state]
      d[char] = dst_node
      if dst_node not in transitions:
        remaining.add(dst_state)

  # explicitly add `invalid_node`, which is otherwise not reachable.
  # `invalid_node` transitions to itself for all characters that do not transition from `start_node`.
  assert invalid_node not in transitions
  invalid_dict = transitions[invalid_node]
  invalid_chars = set(range(0x100)) - set(transitions[start_node])
  for c in invalid_chars:
    invalid_dict[c] = invalid_node

  # generate matchNodeNames.
  all_node_names = defaultdict(set)
  for nfa_state, dfa_node in nfa_states_to_dfa_nodes.items():
    for nfa_node in nfa_state:
      try: name = nfa.matchNodeNames[nfa_node]
      except KeyError: continue
      all_node_names[dfa_node].add(name)
  # prefer literal rules.
  preferred_node_names = { node : (frozenset(n for n in names if n in nfa.literalRules) or frozenset(names))
    for node, names in all_node_names.items() }
  # check for ambiguous rules.
  ambiguous_name_groups = { tuple(sorted(names)) for names in preferred_node_names.values() if len(names) != 1 }
  if ambiguous_name_groups:
    for group in sorted(ambiguous_name_groups):
      errFL('Rules are ambiguous: {}.', ', '.join(group))
    exit(1)
  # create final dictionary.
  matchNodeNames = { node : seq_first(names) for node, names in preferred_node_names.items() }
  # validate.
  assert set(matchNodeNames.values()) == set(nfa.matchNodeNames.values())

  return DFA(transitions=dict(transitions), matchNodeNames=matchNodeNames, literalRules=nfa.literalRules)


def minimizeDFA(dfa):
  # sources:
  # http://www.cs.sun.ac.za/rw711/resources/dfa-minimization.pdf.
  # https://en.wikipedia.org/wiki/DFA_minimization.
  # Note: this implementation of Hopcroft DFA minimization does not use the 'partition refinement' data structure.
  # As a result it is noticeably slow.
  alphabet = dfa.alphabet
  # start with a rough partition; match nodes are all distinct from each other,
  # and non-match nodes form an additional distinct set.
  partitions = {dfa.nonMatchNodes} | {frozenset({n}) for n in dfa.matchNodes}
  remaining = set(partitions) # set of distinguishing sets used in refinement.
  while remaining:
    a = remaining.pop() # a partition.
    for char in alphabet:
      for b in list(partitions): # split `b`; does transition from `b` via `char` lead to a node in `a`?
        refinement = fan_seq_by_pred(b, pred=lambda node: (dfa.transitions[node].get(char) in a))
        # None is never in `a`, so `get` does what we want.
        # note: this splitting operation is where the 'partition refinement' structure is supposed to be used for speed.
        # using cProfile we can see that fan_seq_by_pred takes most the running time for a real-world lexer.
        # TODO: fix this performance bottleneck.
        if not all(refinement): continue # no real refinement; all in one or the other.
        refinement_sets = [frozenset(p) for p in refinement]
        partitions.remove(b)
        partitions.update(refinement_sets)
        if b in remaining:
          remaining.remove(b)
          remaining.update(refinement_sets)
        else:
          # crucial detail for performance:
          # we only need one half of the split to distinguish all partitions;
          # choosing the smaller of the two guarantees low time complexity.
          remaining.add(min(refinement_sets, key=len))

  mapping = {}
  for new_node, part in enumerate(sorted(sorted(p) for p in partitions)):
    for old_node in part:
      mapping[old_node] = new_node

  transitions = defaultdict(dict)
  for old_node, old_d in dfa.transitions.items():
    new_d = transitions[mapping[old_node]]
    for char, old_dst in old_d.items():
      new_dst = mapping[old_dst]
      try:
        existing = new_d[char]
        if existing != new_dst:
          failF('inconsistency in minimized DFA: src state: {}->{}; char: {!r};' +
            'dst state: {}->{} != ?->{}', old_node, new_node, char, old_dst, new_dst, existing)
      except KeyError:
        new_d[char] = new_dst

  matchNodeNames = { mapping[old] : name for old, name in dfa.matchNodeNames.items() }
  return DFA(transitions=dict(transitions), matchNodeNames=matchNodeNames, literalRules=dfa.literalRules)


class FA:
  '''
  Finite Automaton abstract base class.

  Terminology:
  Node: a discrete position in the automaton graph, represented as an integer.
    This is traditionally referred to as a 'state'.
  State: the state of the algorithm while matching an input string against an automaton.
    For DFAs, the state is the current node.
    For NFAs, the state is a set of nodes;
      traditionally this is referred to as "simulating the NFA",
      or the NFA being "in multiple states at once".
  We make the node/state distinction here so that the code and documentation can be more precise,
  at the cost of being less traditional.

  An automaton consists of two parts:
  * transitions: dictionary of node to dictionary of character to destination.
    * for DFAs, the destination is a single node.
    * for NFAs, the destination is a set of nodes, representing a subset of the next state.
  * matchNodeNames: the set of nodes that represent a match, and the corresponding name for each.

  The starting state is always 0 for DFAs, and {0} for NFAs.
  Additionally, 1 and {1} are always the respective invalid states.
  When matching fails, the FA transitions to `invalid`,
  where it will continue matching all characters that are not a transition from `initial`.
  This allows the FA to produce a stream of tokens that completely span any input string.

  `empty` is a reserved state (-1) that represents a nondeterministic jump between NFA nodes.
  '''

  def __init__(self, transitions, matchNodeNames, literalRules):
    self.transitions = transitions
    self.matchNodeNames = matchNodeNames
    self.literalRules = literalRules

  @property
  def allCharToStateDicts(self): return self.transitions.values()

  @property
  def alphabet(self):
    return frozenset().union(*(d.keys() for d in self.allCharToStateDicts)) - {empty}

  @property
  def allSrcNodes(self): return frozenset(self.transitions.keys())

  @property
  def allDstNodes(self):
    return frozenset().union(*(self.dstNodes(node) for node in self.allSrcNodes))

  @property
  def allNodes(self): return self.allSrcNodes | self.allDstNodes

  @property
  def terminalNodes(self): return frozenset(n for n in self.allNodes if not self.transitions.get(n))

  @property
  def matchNodes(self): return frozenset(self.matchNodeNames.keys())

  @property
  def nonMatchNodes(self): return self.allNodes - self.matchNodes

  @property
  def preMatchNodes(self):
    matchNodes = self.matchNodes
    nodes = set()
    remaining = {0}
    while remaining:
      node = remaining.pop()
      assert node not in nodes
      if node in matchNodes: continue
      nodes.add(node)
      remaining.update(self.dstNodes(node) - nodes)
    return frozenset(nodes)

  @property
  def postMatchNodes(self):
    matchNodes = self.matchNodes
    nodes = set()
    remaining = set(matchNodes)
    while remaining:
      node = remaining.pop()
      for dst in self.dstNodes(node):
        if dst not in matchNodes and dst not in nodes:
          nodes.add(dst)
          remaining.add(dst)
    return frozenset(nodes)


  @property
  def ruleNames(self): return frozenset(self.matchNodeNames.values())

  def describe(self, label=None):
    errFL('{}:', label or type(self).__name__)
    errL(' matchNodeNames:')
    for node, name in sorted(self.matchNodeNames.items()):
      errFL('  {}: {}', node, name)
    errL(' transitions:')
    for src, d in sorted(self.transitions.items()):
      errFL('  {}:{}', src, prefix_nonempty(' ', self.matchNodeNames.get(src, '')))
      dst_chars = defaultdict(set)
      for char, dst in d.items():
        dst_chars[dst].add(char)
      dst_sorted_chars = [(dst, sorted(chars)) for (dst, chars) in dst_chars.items()]
      for dst, chars in sorted(dst_sorted_chars, key=lambda p: p[1]):
        errFL('    {} -> {}{}', chars_desc(chars), dst, prefix_nonempty(': ', self.matchNodeNames.get(dst, '')))
    errL()


class NFA(FA):
  'Nondeterministic Finite Automaton.'

  def dstNodes(self, node):
    return frozenset().union(*self.transitions[node].values())

  def validate(self):
    start = self.advanceEmpties({0})
    msgs = []
    for node, name in sorted(self.matchNodeNames.items()):
      if node in start:
        msgs.append('error: rule is trivially matched from start: {}.'.format(name))
    return msgs

  def advance(self, state, char):
    nextState = set()
    for node in state:
      try: dstNodes = self.transitions[node][char]
      except KeyError: pass
      else: nextState.update(dstNodes)
    return self.advanceEmpties(nextState)

  def match(self, input, start=frozenset({0})):
    if is_str(input):
      input = input.encode()
    state = self.advanceEmpties(start)
    #errFL('NFA start: {}', state)
    for char in input:
      state = self.advance(state, char)
      #errFL('NFA step: {} -> {}', bytes([char]), state)
    all_matches = frozenset(dict_filter_map(self.matchNodeNames, state))
    literal_matches = frozenset(n for n in all_matches if n in self.literalRules)
    return literal_matches or all_matches

  def advanceEmpties(self, state):
    remaining = set(state)
    expanded = set()
    while remaining:
      node = remaining.pop()
      expanded.add(node)
      try: dstNodes = self.transitions[node][empty]
      except KeyError: continue
      novel = dstNodes - expanded
      remaining.update(novel)
    return frozenset(expanded)


class DFA(FA):
  'Deterministic Finite Automaton.'

  def dstNodes(self, node):
    return frozenset(self.transitions[node].values())

  def advance(self, state, char):
    return self.transitions[state][char]

  def match(self, input, start=0):
    if is_str(input):
      input = input.encode()
    state = start
    for char in input:
      try: state = self.advance(state, char)
      except KeyError: return None
    return self.matchNodeNames.get(state)



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
    mode = Immutable(name=mode_name, start=remap[0], invalid=remap[1], invalid_name=dfa.matchNodeNames[1])
    modes.append(mode)
    node_modes.update((node, mode) for node in remap.values())
    def remap_trans_dict(d): return { c : remap[dst] for c, dst in d.items() }
    transitions.update((remap[src], remap_trans_dict(d)) for src, d in sorted(dfa.transitions.items()))
    matchNodeNames.update((remap[node], name) for node, name in sorted(dfa.matchNodeNames.items()))
    literalRules.update(dfa.literalRules)
  return (DFA(transitions=transitions, matchNodeNames=matchNodeNames, literalRules=literalRules), modes, node_modes)


def output(dfa, modes, node_modes, mode_transitions, rules_path, path, test, type_prefix, license):
  name = path_name_stem(rules_path)
  ext = path_ext(path)
  supported_exts = ['.swift']
  if ext not in supported_exts:
    failF('output path has unknown extension {!r}; supported extensions are: {}.',
      ext, ', '.join(supported_exts))
  if ext == '.swift':
    output_swift(dfa=dfa, modes=modes, node_modes=node_modes, mode_transitions=mode_transitions,
      rules_path=rules_path, path=path, test=test, type_prefix=type_prefix, license=license)


def chars_desc(chars):
  return ' '.join(char_descriptions[c] for c in sorted(chars))


char_descriptions = {i : '{:02x}'.format(i) for i in range(0x100)}

char_descriptions.update({
  -1: 'Ø',
  ord('\a'): '\\a',
  ord('\b'): '\\b',
  ord('\t'): '\\t',
  ord('\n'): '\\n',
  ord('\v'): '\\v',
  ord('\f'): '\\f',
  ord('\r'): '\\r',
  ord(' '): '\_',
})

char_descriptions.update((i, chr(i)) for i in range(ord('!'), 0x7f))


if __name__ == "__main__": main()
