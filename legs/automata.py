# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import defaultdict
from itertools import chain, count

from pithy.dict_utils import dict_filter_map
from pithy.io import errFL, errL, failF
from pithy.seq import seq_first
from pithy.type_util import is_str


empty_symbol = -1 # not a legitimate byte value.


class FA:
  '''
  Finite Automaton abstract base class.
  NFA/DFA implementation derived from http://www-bcf.usc.edu/~breichar/teaching/2011cs360/NFAtoDFA.py.

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
  * transitions: dictionary of source node to (dictionary of byte to destination node).
    * for DFAs, the destination is a single node.
    * for NFAs, the destination is a set of nodes, representing a subset of the next state.
  * matchNodeNames: the set of nodes that represent a match, and the corresponding name for each.

  The starting state is always 0 for DFAs, and {0} for NFAs.
  Additionally, 1 and {1} are always the respective invalid states.
  When matching fails, the FA transitions to `invalid`,
  where it will continue matching all bytes that are not a transition from `initial`.
  This allows the FA to produce a stream of tokens that completely span any input string.

  `empty_symbol` is a reserved value (-1 is not part of the byte alphabet)
  that represents a nondeterministic jump between NFA nodes.
  '''

  def __init__(self, transitions, matchNodeNames, literalRules):
    self.transitions = transitions
    self.matchNodeNames = matchNodeNames
    self.literalRules = literalRules

  @property
  def allBytetoStateDicts(self): return self.transitions.values()

  @property
  def alphabet(self):
    return frozenset().union(*(d.keys() for d in self.allBytetoStateDicts)) - {empty_symbol}

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
      dst_bytes = defaultdict(set)
      for byte, dst in d.items():
        dst_bytes[dst].add(byte)
      dst_sorted_bytes = [(dst, sorted(byte_set)) for (dst, byte_set) in dst_bytes.items()]
      for dst, byte_set in sorted(dst_sorted_bytes, key=lambda p: p[1]):
        errFL('    {} ==> {}{}', codes_desc(byte_set), dst, prefix_nonempty(': ', self.matchNodeNames.get(dst, '')))
    errL()

  def describe_stats(self, label=None):
    errFL('{}:', label or type(self).__name__)
    errFL('  matchNodeNames: {}', len(self.matchNodeNames))
    errFL('  nodes: {}', len(self.transitions))
    errFL('  transitions: {}', sum(len(d) for d in self.transitions.values()))
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

  def advance(self, state, byte):
    nextState = set()
    for node in state:
      try: dstNodes = self.transitions[node][byte]
      except KeyError: pass
      else: nextState.update(dstNodes)
    return self.advanceEmpties(nextState)

  def match(self, text, start=frozenset({0})):
    if is_str(text):
      text = text.encode()
    state = self.advanceEmpties(start)
    #errFL('NFA start: {}', state)
    for byte in text:
      state = self.advance(state, byte)
      #errFL('NFA step: {} -> {}', bytes([byte]), state)
    all_matches = frozenset(dict_filter_map(self.matchNodeNames, state))
    literal_matches = frozenset(n for n in all_matches if n in self.literalRules)
    return literal_matches or all_matches

  def advanceEmpties(self, state):
    remaining = set(state)
    expanded = set()
    while remaining:
      node = remaining.pop()
      expanded.add(node)
      try: dstNodes = self.transitions[node][empty_symbol]
      except KeyError: continue
      novel = dstNodes - expanded
      remaining.update(novel)
    return frozenset(expanded)



class DFA(FA):
  'Deterministic Finite Automaton.'

  def dstNodes(self, node):
    return frozenset(self.transitions[node].values())

  def advance(self, state, byte):
    return self.transitions[state][byte]

  def match(self, text, start=0):
    if is_str(text):
      text = text.encode()
    state = start
    for byte in text:
      try: state = self.advance(state, byte)
      except KeyError: return None
    return self.matchNodeNames.get(state)



def genDFA(nfa):
  '''
  Generate a DFA from an NFA.

  Internally, a DFA node is equivalent to a set of NFA nodes.
  Note that this is easily confused with an NFA state (also a set of NFA nodes).
  A DFA has a node for every reachable subset of nodes in the corresponding NFA.
  In the worst case, there will be an exponential increase in number of nodes.

  Unlike the NFA, the DFA's operational state is just a single node value.

  For each DFA node, there is a mapping from byte values to destination nodes.
  Generating a lexer from a DFA is straightforward:
  switch on the current state, and then for each node, switch on the current byte.
  If the switch defaults, flush the pending token (either the matching kind or `incomplete`),
  and then performs the start transition.

  The `start` node is a special case; its default clause transitions to the `invalid` state.
  `invalid` is a match state which transitions to itself for all characters that are not valid start characters.
  `incomplete` is not itself a state, but rather a token kind distinct from `invalid`,
  indicating a token that began to match but then defaulted before reaching a match state.
  This distinction is important for error reporting;
  lexical errors are found at the ends of `incomplete` nodes and the starts of `invalid` nodes.

  Note that the `invalid` node is not reachable from `start` in the DFA;
  we rely on the generated lexer to default into the invalid state.
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

  # explicitly add transitions from `invalid_node`, which is otherwise not reachable.
  # `invalid_node` transitions to itself for all characters that do not transition from `start_node`.
  assert invalid_node not in transitions
  invalid_dict = transitions[invalid_node]
  invalid_chars = set(range(0x100)) - set(transitions[start_node])
  for c in invalid_chars:
    invalid_dict[c] = invalid_node

  # generate matchNodeNames.
  # nodes may match more than one rule when the rules overlap.
  # we prefer 'literal' rules over others, but otherwise overlaps are treated as ambiguity errors.
  all_node_names = defaultdict(set) # nodes to sets of names.
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
  '''
  Optimize a DFA by coalescing redundant states.
  sources:
  * http://www.cs.sun.ac.za/rw711/resources/dfa-minimization.pdf.
  * https://en.wikipedia.org/wiki/DFA_minimization.
  * https://www.ics.uci.edu/~eppstein/PADS/PartitionRefinement.py
  '''
  alphabet = dfa.alphabet
  # start with a rough partition; match nodes are all distinct from each other,
  # and non-match nodes form an additional distinct set.
  init_sets = [{n} for n in dfa.matchNodes] + [set(dfa.nonMatchNodes)]

  sets = { id(s): s for s in init_sets }
  partition = { n: s for s in sets.values() for n in s }

  rev_transitions = defaultdict(lambda: defaultdict(set))
  for src, d in dfa.transitions.items():
    for char, dst in d.items():
      rev_transitions[dst][char].add(src)

  def refine(refining_set):
    '''
    Given refining set B,
    Refine each set A in the partition to a pair of sets: A & B and A - B.
    Return a list of pairs for each changed set;
    one of these is a new set, the other is the mutated original.
    '''
    part_sets_to_intersections = defaultdict(set)
    set_pairs = []
    for node in refining_set:
      s = partition[node]
      part_sets_to_intersections[id(s)].add(node)
    for id_s, intersection in part_sets_to_intersections.items():
      s = sets[id_s]
      if intersection != s:
        sets[id(intersection)] = intersection
        for x in intersection:
          partition[x] = intersection
        s -= intersection
        set_pairs.append((intersection, s))
    return set_pairs

  remaining = list(init_sets) # distinguishing sets used to refine the partition.
  while remaining:
    a = remaining.pop() # a partition.
    for char in alphabet:
      # find all nodes `m` that transition via `char` to any node `n` in `a`.
      dsts = set(chain.from_iterable(rev_transitions[node][char] for node in a))
      #dsts_brute = [node for node in partition if dfa.transitions[node].get(char) in a] # brute force version is slow.
      #assert set(dsts_brute) == dsts
      len_dsts = len(dsts)
      if len_dsts == 0 or len_dsts == len(partition): continue # no refinement.
      for new, old in refine(dsts):
        if len(new) < len(old): # prefer new.
          if new not in remaining: remaining.append(new)
          elif old not in remaining: remaining.append(old)
        else: # prefer old.
          if old not in remaining: remaining.append(old)
          elif new not in remaining: remaining.append(new)

  mapping = {}
  for new_node, part in enumerate(sorted(sorted(p) for p in partition.values())):
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
          failF('inconsistency in minimized DFA: src state: {}->{}; char: {!r}; dst state: {}->{} != ?->{}',
            old_node, new_node, char, old_dst, new_dst, existing)
      except KeyError:
        new_d[char] = new_dst

  matchNodeNames = { mapping[old] : name for old, name in dfa.matchNodeNames.items() }
  return DFA(transitions=dict(transitions), matchNodeNames=matchNodeNames, literalRules=dfa.literalRules)

