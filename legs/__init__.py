#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# NFA/DFA implementation derived from http://www-bcf.usc.edu/~breichar/teaching/2011cs360/NFAtoDFA.py.

import re

from argparse import ArgumentParser
from collections import defaultdict
from itertools import count

from pithy.collection_utils import freeze
from pithy.dicts import dict_filter_map, dict_put
from pithy.fs import split_dir_stem_ext
from pithy.io import errF, errFL, errL, failF, outFL
from pithy.seq import group_seq_by_index
from pithy.type_util import is_str

from legs.swift import output_swift


def main():
  parser = ArgumentParser()
  parser.add_argument('rules_path')
  parser.add_argument('-dbg', action='store_true')
  parser.add_argument('-match', nargs='+')
  parser.add_argument('-output')
  parser.add_argument('-test')
  parser.add_argument('-license', default='NO LICENSE SPECIFIED')
  args = parser.parse_args()
  dbg = args.dbg
  
  rules = compile_rules(args.rules_path)
  if dbg:
    for rule in rules:
      rule.describe()
    errL()

  nfa = genNFA(rules)
  if dbg: nfa.describe()
  
  msgs = nfa.validate()
  if msgs:
    for m in msgs:
      errL(m)
    exit(1)
  
  fat_dfa = genDFA(nfa)
  if dbg: fat_dfa.describe('Fat DFA')
  
  min_dfa = minimizeDFA(fat_dfa)
  if dbg: min_dfa.describe('Min DFA')
  
  if args.match is not None:
    for string in args.match:
      match_string(nfa, fat_dfa, min_dfa, string)

  if args.output is not None:
    output(dfa=min_dfa, rules_path=args.rules_path, path=args.output, test_path=args.test, license=args.license)


def match_string(nfa, fat_dfa, min_dfa, string):
  'Test `nfa`, `min_dfa`, and `dfa` against each other by attempting to match `string`.'
  nfa_matches = nfa.match(string)
  if len(nfa_matches) > 1:
    failF('match: {!r}: NFA matched multiple rules: {}', string, nfa_matches)
  nfa_match = list(nfa_matches)[0] if nfa_matches else None
  fat_dfa_match = fat_dfa.match(string)
  if fat_dfa_match != nfa_match:
    failF('match: {!r} inconsistent match: NFA: {}; fat DFA: {}.', string, nfa_match, fat_dfa_match)
  min_dfa_match = min_dfa.match(string)
  if min_dfa_match != nfa_match:
    failF('match: {!r} inconsistent match: NFA: {}; min DFA: {}.', string, nfa_match, min_dfa_match)  
  outFL('match: {!r} {} {}', string, *(('->', nfa_match) if nfa_match else ('--', 'none')))


def compile_rules(path):
  'Compile the rules given in the legs file at `path`.'
  rules = []
  for line_num, line in enumerate(open(path)):
    line = line.rstrip()
    if not line or line.startswith('#'): continue
    colon_match = re.search(': *', line)
    if colon_match:
      name = line[:colon_match.start()].strip()
      start_col = colon_match.end()
    else: # derive a name from the rule; meant for convenience while testing.
      name = re.sub('\W+', '_', line.strip())
      if name[0].isdigit():
        name = '_' + name
      start_col = 0
    if name == 'invalid':
      parse_failF((path, line_num, 1, line), 'rule name is reserved: {!r}.', name)
    rule = parse_rule_pattern(path, name, line_num, start_col=start_col, pattern=line)
    rules.append(rule)
  return rules


def parse_rule_pattern(path, name, line_num, start_col, pattern):
  'Parse a single pattern and return a Rule object.'
  parser_stack = [PatternParser((path, line_num, 0, pattern), isParenParser=False)]
  # stack of parsers, one for each open nesting syntactic element '(', etc.
  escape = False
  for col_num, c in enumerate(pattern):
    if col_num < start_col: continue
    pos = (path, line_num, col_num, pattern)
    parser = parser_stack[-1]
    if escape:
      escape = False
      try: escaped_chars = escape_char_sets[c]
      except KeyError: parse_failF(pos, 'invalid escaped character: {!r}', c)
      else: parser.parse_escaped(pos, escaped_chars)
    elif c == '\\':
      escape = True
    elif c == ' ':
      continue
    elif c == parser.terminator:
      parser_stack.pop()
      parent = parser_stack[-1]
      parent.receive(parser.finish())
    else:
      child = parser.parse(pos, c)
      if child:
        parser_stack.append(child)
  parser = parser_stack.pop()
  if parser_stack:
    parse_failF((path, line_num, col_num + 1, pattern), 'expected terminator: {!r}', parser.terminator) 
  rule = parser.finish()
  rule.name = name
  return rule


def parse_failF(pos, fmt, *items):
  'Print a formatted parsing failure to std err and exit.'
  path, line, col, contents = pos
  failF('{}:{}:{}: ' + fmt + '\n{}\n{}^', path, line + 1, col + 1, *items, contents, ' ' * col)

def chr_ranges(*intervals):
  "Return a `bytes` object containing the range of characters denoted by `pairs`, e.g. `b'AZ'`."
  points = frozenset().union(*(range(i, j + 1) for i, j in intervals))
  return bytes(sorted(points))


escape_char_sets = {
  'd': chr_ranges(b'09'),
  'l': chr_ranges(b'az', b'AZ'), # nonstandard 'letter' escape.
  'w': chr_ranges(b'az', b'AZ', b'09'),
  'n': b'\n',
  't': b'\t',
  '_': b' ', # nonstandard space escape.
}
escape_char_sets.update((c, c.encode()) for c in '[]{}()\\')

#for k, v in escape_char_sets.items():
#  errFL('{}: {!r}', k, v)


class PatternParser:

    def __init__(self, pos, isParenParser):
      self.pos = pos
      self.terminator = ')' if isParenParser else None
      self.choices = []
      self.seq = []
      self.seq_pos = pos
    
    def parse(self, pos, c):
      if c == '(':
        return PatternParser(pos, isParenParser=True)
      elif c == '[':
        return CharsetParser(pos)
      elif c == '|':
        self.flush_seq(pos)
      elif c == '?': self.quantity(pos, c, Opt)
      elif c == '*': self.quantity(pos, c, Star)
      elif c == '+': self.quantity(pos, c, Plus)
      else:
        self.seq.append(Char(pos, chars=bytes([ord(c)])))
    
    def parse_escaped(self, pos, chars):
      self.seq.append(Char(pos, chars=chars))
    
    def finish(self):
      self.flush_seq(pos=None)
      choices = self.choices
      return choices[0] if len(choices) == 1 else Choice(self.pos, subs=tuple(choices))

    def flush_seq(self, pos):
      seq = self.seq
      if not seq: parse_failF(self.seq_pos, 'empty sequence.')
      rule = seq[0] if len(seq) == 1 else Seq(self.seq_pos, subs=tuple(seq))
      self.choices.append(rule)
      self.seq = []
      self.seq_pos = pos

    def quantity(self, pos, char, T):
      try: el = self.seq.pop()
      except IndexError: parse_failF(pos, "'{}' does not follow any pattern.", char)
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
    self.chars.add(ord(c))

  def parse_escaped(self, pos, escaped_chars):
    self.chars.update(escaped_chars)  
  
  def finish(self):
    chars = set(range(256)) - self.chars if self.invert else self.chars
    return Char(self.pos, chars=bytes(sorted(chars)))


empty = -1

class Rule:
  def __init__(self, pos, chars=None, subs=None):
    if chars is None:
      assert isinstance(subs, tuple)
      for sub in subs: assert isinstance(sub, Rule)
    elif subs is None:
      assert isinstance(chars, bytes)
      if not chars: parse_failF(pos, 'empty character set.')
    else: failF('chars and subs are mutually exclusive.')
    self.name = None
    self.pos = pos
    self.chars = chars
    self.subs = subs

  def describe(self, depth=0):
    _, line, col, _ = self.pos
    n = self.name + ' ' if self.name else ''
    errF('{}{}{}:{}:{}:', '  ' * depth, n, type(self).__name__, line + 1, col + 1)
    if self.chars is not None:
      errL(' ', self.chars)
    else:
      errL()
      for sub in self.subs:
        sub.describe(depth + 1)


class Choice(Rule):
  def genNFA(self, mk_node, transitions, start, end):
    for choice in self.subs:
      choice.genNFA(mk_node, transitions, start, end)


class Seq(Rule):
  def genNFA(self, mk_node, transitions, start, end):
    subs = self.subs
    last_idx = len(subs) - 1
    prev = start
    for i, el in enumerate(subs):
      next_ = end if (i == last_idx) else mk_node()
      el.genNFA(mk_node, transitions, prev, next_)
      prev = next_


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


class Char(Rule):
  def genNFA(self, mk_node, transitions, start, end):
    d = transitions[start]
    for char in self.chars:
      d[char].add(end)


def genNFA(rules):
  '''
  Generate an NFA from `rules`.
  The NFA can be used to match against an argument string,
  but cannot produce a token stream directly.
  The 'invalid' node is always added at index 1, and is always unreachable.
  See genDFA for more details about 'invalid'. 
  '''

  indexer = iter(count())
  def mk_node(): return next(indexer)

  start = mk_node() # always 0.
  invalid = mk_node() # always 1. not used; simply reserving the number for clarity.
  matchNodeNames = {}
  transitions = defaultdict(lambda: defaultdict(set))
  dict_put(matchNodeNames, invalid, 'invalid')
  for rule in sorted(rules, key=lambda rule: rule.name):
    matchNode = mk_node()
    rule.genNFA(mk_node, transitions, start, matchNode)
    assert rule.name
    if rule.name in matchNodeNames:
      failF('duplicate rule name: {!r}', rule.name)
    matchNodeNames[matchNode] = rule.name
  return NFA(transitions=freeze(transitions), matchNodeNames=matchNodeNames)


def genDFA(nfa):
  '''  
  A DFA node is equivalent to a set of NFA nodes.
  A DFA a node for every reachable subset of nodes in the corresponding NFA.
  In the worst case, there will be an exponential increase in number of nodes.
  
  As in the NFA, the 'invalid' node is unreachable,
  but we explicitly add transitions from 'invalid' to itself,
  for all characters that are not transitions out of the 'start' state.
  This allows the generated lexer code to use simpler switch default clauses.
  For each state, the lexer switches on the current byte.
  If the switch defaults, we flush any pending token (as set by the last match state), and then:
  * for match states, perform the start transition as if we were at the start state.
  * for nonmatch states: advance to `invalid`.
  `invalid` is itself a match state, so once a valid character is encountered,
  the lexer emits an 'invalid' token and resets.
  '''

  indexer = iter(count())
  def mk_node(): return next(indexer)

  nfa_states_to_dfa_nodes = defaultdict(mk_node)
  start = frozenset(nfa.advanceEmpties({0}))
  invalid = frozenset({1}) # no need to expand as `invalid` is never reachable.
  start_node = nfa_states_to_dfa_nodes[start]
  invalid_node = nfa_states_to_dfa_nodes[invalid]

  transitions = defaultdict(dict)
  alphabet = nfa.alphabet
  remaining = {start}
  while remaining:
    state = remaining.pop()
    node = nfa_states_to_dfa_nodes[state]
    d = transitions[node] # unlike NFA, DFA dictionary contains all valid states as keys.
    for char in alphabet:
      dst_state = frozenset(nfa.advance(state, char))
      if not dst_state: continue # do not add empty sets for brevity.
      dst_node = nfa_states_to_dfa_nodes[dst_state]
      d[char] = dst_node
      if dst_node not in transitions:
        remaining.add(dst_state)

  # explicitly add `invalid`, which is otherwise not reachable.
  # `invalid` transitions to itself for all characters that do not transition from `start`. 
  assert invalid_node not in transitions
  invalid_dict = transitions[invalid_node]
  invalid_chars = set(range(0x100)) - set(transitions[start_node])
  for c in invalid_chars:
    invalid_dict[c] = invalid_node
  
  # generate matchNodeNames.
  matchNodeNames = {}
  for state, node in sorted(nfa_states_to_dfa_nodes.items()):
    for nfaNode, name, in nfa.matchNodeNames.items():
      if nfaNode in state:
        if node in matchNodeNames:
          failF('Rules are ambiguous: {}, {}.', name, matchNodeNames[node])
        matchNodeNames[node] = name

  # validate.
  allNames = set(matchNodeNames.values())
  for name in nfa.matchNodeNames.values():
    if name not in allNames:
      failF('Rule is not reachable in DFA: {}', name)
  return DFA(transitions=dict(transitions), matchNodeNames=matchNodeNames)



def minimizeDFA(dfa):
  # sources:
  # http://www.cs.sun.ac.za/rw711/resources/dfa-minimization.pdf.
  # https://en.wikipedia.org/wiki/DFA_minimization.
  # Note: this implementation of Hopcroft DFA minimization does not use the 'partition refinement' data structure.
  # As a result I expect that its time complexity is suboptimal.
  alphabet = dfa.alphabet
  # start with a rough partition; match nodes are all distinct from each other,
  # and non-match nodes form an additional distinct set.
  nonMatchNodes = dfa.allNodes - dfa.matchNodes
  partitions = {nonMatchNodes} | {frozenset({n}) for n in dfa.matchNodes}
  remaining = set(partitions) # set of distinguishing sets used in refinement.
  while remaining:
    a = remaining.pop() # a partition.
    for char in alphabet:
      for b in list(partitions): # split `b`; does transition from `b` via `char` lead to a node in `a`?
        # note: this splitting operation is where the 'partition refinement' structure is supposed to be used for speed.
        refinement = ([], [])
        for node in b:
          index = int(dfa.transitions[node].get(char) in a) # None is never in `a`, so `get` does what we want.
          refinement[index].append(node)
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
  return DFA(transitions=dict(transitions), matchNodeNames=matchNodeNames)


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

  def __init__(self, transitions, matchNodeNames):
    self.transitions = transitions
    self.matchNodeNames = matchNodeNames

  @property
  def allCharToStateDicts(self): return self.transitions.values()

  @property
  def alphabet(self):
    return frozenset().union(*(d.keys() for d in self.allCharToStateDicts)) - {empty}

  @property
  def allSrcNodes(self): return frozenset(self.transitions.keys())

  @property
  def allNodes(self): return self.allSrcNodes | self.allDstNodes

  @property
  def matchNodes(self): return frozenset(self.matchNodeNames.keys())

  def describe(self, label=None):
    errFL('{}:', label or type(self).__name__)
    errL(' matchNodeNames:')
    for node, name in sorted(self.matchNodeNames.items()):
      errFL('  {}: {}', node, name)
    errL(' transitions:')
    for src, d in sorted(self.transitions.items()):
      errFL('  {}:', src)
      dst_chars = defaultdict(set)
      for char, dst in d.items():
        dst_chars[dst].add(char)
      dst_sorted_chars = [(dst, sorted(chars)) for (dst, chars) in dst_chars.items()]
      for dst, chars in sorted(dst_sorted_chars, key=lambda p: p[1]):
        errFL('    {} -> {}', chars_desc(chars), dst)
    errL()


class NFA(FA):
  'Nondeterministic Finite Automaton.'

  @property
  def allDstNodes(self):
    s = set()
    for d in self.allCharToStateDicts:
      s.update(*d.values())
    return frozenset(s)

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
    return frozenset(dict_filter_map(self.matchNodeNames, state))

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

  @property
  def allDstNodes(self):
    s = set()
    for d in self.allCharToStateDicts:
      s.update(d.values())
    return frozenset(s)

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


def output(dfa, rules_path, path, test_path, license):
  dir, stem, ext = split_dir_stem_ext(path)
  supported_exts = ['.swift']
  if ext not in supported_exts:
    failF('output path has unknown extension {!r}; supported extensions are: {}.',
      ext, ', '.join(supported_exts))
  if ext == '.swift':
    output_swift(dfa=dfa, rules_path=rules_path, path=path, test_path=test_path,
      license=license, stem=stem)


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
