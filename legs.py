#!/usr/bin/env python3

# derived from http://www-bcf.usc.edu/~breichar/teaching/2011cs360/NFAtoDFA.py.

import re

from argparse import ArgumentParser
from pithy import *
from pithy.collection_utils import freeze
from pithy.lists import list_push_index


def main():
  
  parser = ArgumentParser()
  parser.add_argument('rules_path')
  parser.add_argument('-dbg', action='store_true')
  parser.add_argument('-match', nargs='+')
  parser.add_argument('-output', nargs='?')
  args = parser.parse_args()
  dbg = args.dbg
  
  rules = compile_rules(args.rules_path)
  if dbg:
    for rule in rules:
      rule.describe()
    errL()

  nfa = genNFA(rules)
  if dbg:
    nfa.describe()
    errL()
  
  msgs = nfa.validate()
  if msgs:
    for m in msgs:
      errL(m)
    exit(1)
  
  dfa = nfa.genDFA()
  if dbg:
    dfa.describe()
  
  if args.match is not None:
    for string in args.match:
      if dbg: errFL('matching: {!r}', string)
      nfa_matches = nfa.match(string)
      dfa_match = dfa.match(string)
      len_dfa = 1 if dfa_match else 0
      if len(nfa_matches) != len_dfa or (dfa_match and dfa_match not in nfa_matches):
        failF('inconsistent match results: NFA: {}; DFA: {}.', nfa_matches, dfa_match)
      outFL('match: {!r} -{} {}', string,
        *(('>', dfa_match) if dfa_match else ('-', 'none')))

  elif args.output is not None:
    dfa.output(args.output)



def compile_rules(path):
  rules = []
  for line_num, line in enumerate(open(path)):
    line = line.rstrip()
    if not line or line.startswith('#'): continue
    pos = (path, line_num, 1, line)
    colon_match = re.search(': *', line)
    if colon_match:
      name = line[:colon_match.start()].strip()
      start_col = colon_match.end()
    else:
      name = line.strip()
      start_col = 0
    rule = parse_rule_pattern(path, name, line_num, start_col=start_col, pattern=line)
    rules.append(rule)
  return rules


def parse_rule_pattern(path, name, line_num, start_col, pattern):
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
  path, line, col, contents = pos
  failF('{}:{}:{}: ' + fmt + '\n{}\n{}^', path, line + 1, col + 1, *items, contents, ' ' * col)

def chr_ranges(*pairs):
  points = frozenset().union(*(range(p[0], p[1] + 1) for p in pairs))
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
    else: failF('chars and subs are mutually exclusive.')
    self.name = None
    self.pos = pos
    self.chars = chars
    self.subs = subs

  def describe(self, depth=0):
    _, line, col, _ = self.pos
    n = self.name + ' ' if self.name else ''
    errF('{}{}{}:{}:{}:', '  ' * depth, n, type(self).__name__, line + 1, col + 1)
    if self.chars:
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
  nodes = []
  def mk_node(): return list_push_index(nodes)
  start = mk_node()
  matchNodeNames = {}
  transitions = defaultdict(lambda: defaultdict(set))
  for rule in rules:
    matchNode = mk_node()
    rule.genNFA(mk_node, transitions, start, matchNode)
    assert rule.name
    dict_put(matchNodeNames, matchNode, rule.name)
  return NFA(transitions=freeze(transitions), matchNodeNames=matchNodeNames)


class FA:
  '''
  Finite Automaton abstract base class.
  Terminology:
  Node: a discrete position in the automaton graph.
    This is traditionally referred to as a 'state'.
    For NFAs, nodes are integers; for DFAs, they are frozensets of integers.
  State: the state value at a given moment while matching an input string against an automaton.
    For DFAs, states are equivalent to nodes.
    For NFAs, the state of the matching algorithm is a set of states;
      traditionally this is referred to as "simulating the NFA",
      or the NFA being "in multiple states at once".
    Thus, states are frozensets of integers for both subclasses.
  We make the node/state distinction here so that the code and documentation can be more precise,
  at the cost of being less traditional.
  '''

  def __init__(self, transitions, matchNodeNames, startState):
    self.transitions = transitions
    self.matchNodeNames = matchNodeNames
    self.startState = startState
    # validate transitions.
    for charToStateDict in self.allCharToStateDicts:
      for state in charToStateDict.values():
        assert isinstance(state, frozenset)
        assert all(isinstance(i, int) for i in state)

  @property
  def allCharToStateDicts(self): return self.transitions.values()

  @property
  def alphabet(self):
    return set().union(*(d.keys() for d in self.allCharToStateDicts)) - {empty}

  def describe(self):
    errFL('{}:', type(self).__name__)
    errL(' matchNodeNames:')
    for node, name in sorted(self.matchNodeNames.items(), key=lambda p: p[1]):
      errFL('  {}: {}', state_desc(node), name)
    errL(' transitions:')
    for srcNode, d in sorted(self.transitions.items()):
      errFL('  {}:', state_desc(srcNode))
      dstStateChars = defaultdict(set)
      for char, dstState in d.items():
        t = tuple(sorted(dstState))
        dstStateChars[t].add(char)
      for dstState, chars in sorted(dstStateChars.items(), key=lambda p: p[1]):
        errFL('    {} -> {}', chars_desc(chars), state_desc(dstState))


class DFA(FA):
  'Deterministic Finite Automata.'

  def advance(self, state, char):
    return self.transitions[state][char]

  def match(self, input, startState=None):
    if is_str(input):
      input = input.encode()
    state = startState or self.startState
    for char in input:
      try: state = self.advance(state, char)
      except KeyError: return None
    return self.matchNodeNames.get(state, None)


class NFA(FA):
  'Nondeterministic Finite Automata.'

  class TrivialRuleError(Exception): pass

  def __init__(self, transitions, matchNodeNames):
    super().__init__(transitions, matchNodeNames, startState=frozenset({0}))
  
  def validate(self):
    start = self.expandStateViaEmpties(self.startState)
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
    return self.expandStateViaEmpties(nextState)

  def match(self, input, startState=None):
    if is_str(input):
      input = input.encode()
    state = startState or self.startState
    state = self.expandStateViaEmpties(state)
    for char in input:
      #errF('NFA {} {} -> ', state_desc(state), char_descriptions[char]) 
      state = self.advance(state, char)
      #errL(state_desc(state))
    return set(dict_filter_map(self.matchNodeNames, state))

  def expandStateViaEmpties(self, state):
    remaining = set(state)
    expanded = set()
    while remaining:
      node = remaining.pop()
      expanded.add(node)
      try: dstNodes = self.transitions[node][empty]
      except KeyError: continue
      novel = dstNodes - expanded
      remaining.update(novel)
    return expanded

  @property
  def allSrcNodes(self): return set(self.transitions.keys())

  @property
  def allDstNodes(self):
    s = set()
    for d in self.allCharToStateDicts:
      s.update(*d.values())
    return s

  @property
  def allNodes(self): return self.allSrcNodes | self.allDstNodes

  def genDFA(self):
    '''  
    A DFA node/state is a frozenset of NFA nodes.
    A DFA has a node/state for every reachable subset of nodes in its corresponding NFA.
    In the worst case, there will be an exponential increase in number of nodes.
    '''
    transitions = defaultdict(dict)
    startState = frozenset(self.expandStateViaEmpties(self.startState))
    alphabet = self.alphabet
    remainingStates = {startState}
    completedStates = set()
    while remainingStates:
      state = remainingStates.pop()
      completedStates.add(state)
      for char in alphabet:
        dstState = frozenset(self.advance(state, char))
        #errFL('GENDFA {} -- {} -> {}', state_desc(state), char_descriptions[char], state_desc(dstState))
        if not dstState: continue
        transitions[state][char] = dstState
        if dstState not in completedStates: 
          remainingStates.add(dstState)
    matchNodeNames = {}
    for state in completedStates:
      for nfaNode, name, in self.matchNodeNames.items():
        if nfaNode in state:
          #errSL('GEN-DFA matchNodeNames', name, nfaNode, '->', state_desc(state))
          dict_put(matchNodeNames, state, name)
    allNames = set(matchNodeNames.values())
    # validate.
    for name in self.matchNodeNames.values():
      if name not in allNames:
        failF('NFA rule is missing from DFA: {}', name)
    return DFA(transitions=transitions, matchNodeNames=matchNodeNames, startState=startState)


def state_desc(state):
  if is_int(state): return str(state)
  return ' '.join(str(i) for i in sorted(state))

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


if __name__ == "__main__":
  main()
