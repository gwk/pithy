# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Finite Automata.
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
* transitions: dictionary of source node to (dictionary of byte to destination).
  * for DFAs, the destination is a single node.
  * for NFAs, the destination is a set of nodes, representing a subset of the next state.
* matchNodeNameSets: dictionary of nodes mapping matching nodes to the set of corresponding rule names.

The starting state is always 0 for DFAs, and {0} for NFAs.
Additionally, 1 and {1} are always the respective invalid states.

For all bytes that do not naturally transition out of `start`,
artificial transitions are added from `start` to `invalid`,
and `invalid` transitions to itself for all bytes that are not a transition from `start`.
This trick allows the FA to always progress from the start state,
thus producing a stream of tokens that completely span any input string.
'''

from collections import defaultdict
from itertools import chain
from typing import *

from pithy.io import errL, errSL
from pithy.iterable import first_el, int_tuple_ranges
from pithy.string import prepend_to_nonempty

from .codepoints import codes_desc


DfaState = int
DfaStateTransitions = Dict[int, DfaState]
DfaTransitions = Dict[int, DfaStateTransitions]


class DFA:
  'Deterministic Finite Automaton.'

  def __init__(self, transitions: DfaTransitions, matchNodeNameSets: Dict[int, FrozenSet[str]], literalRules: Set[str]) -> None:
    self.transitions = transitions
    self.matchNodeNameSets = matchNodeNameSets
    self.literalRules = literalRules

  @property
  def isEmpty(self) -> bool:
    return not self.transitions

  @property
  def allByteToStateDicts(self) -> Iterable[DfaStateTransitions]: return self.transitions.values()

  @property
  def alphabet(self) -> FrozenSet[int]:
    a: Set[int] = set()
    a.update(*(d.keys() for d in self.allByteToStateDicts))
    return cast(FrozenSet[int], frozenset(a)) # mypy bug.

  @property
  def allSrcNodes(self) -> FrozenSet[int]: return frozenset(self.transitions.keys())

  @property
  def allDstNodes(self) -> FrozenSet[int]:
    s: Set[int] = set()
    s.update(*(self.dstNodes(node) for node in self.allSrcNodes))
    return frozenset(s)

  @property
  def allNodes(self) -> FrozenSet[int]: return self.allSrcNodes | self.allDstNodes

  @property
  def terminalNodes(self) -> FrozenSet[int]: return frozenset(n for n in self.allNodes if not self.transitions.get(n))

  @property
  def matchNodes(self) -> FrozenSet[int]: return frozenset(self.matchNodeNameSets.keys())

  @property
  def nonMatchNodes(self) -> FrozenSet[int]: return self.allNodes - self.matchNodes

  @property
  def preMatchNodes(self) -> FrozenSet[int]:
    if self.isEmpty:
      return frozenset() # empty.
    matchNodes = self.matchNodes
    nodes: Set[int] = set()
    remaining = {0}
    while remaining:
      node = remaining.pop()
      assert node not in nodes
      if node in matchNodes: continue
      nodes.add(node)
      remaining.update(self.dstNodes(node) - nodes)
    return frozenset(nodes)

  @property
  def postMatchNodes(self) -> FrozenSet[int]:
    matchNodes = self.matchNodes
    nodes: Set[int] = set()
    remaining = set(matchNodes)
    while remaining:
      node = remaining.pop()
      for dst in self.dstNodes(node):
        if dst not in matchNodes and dst not in nodes:
          nodes.add(dst)
          remaining.add(dst)
    return frozenset(nodes)

  @property
  def ruleNames(self) -> FrozenSet[str]: return frozenset().union(*self.matchNodeNameSets.values()) # type: ignore

  def describe(self, label=None) -> None:
    errL(label or type(self).__name__, ':')
    errL(' matchNodeNameSets:')
    for node, names in sorted(self.matchNodeNameSets.items()):
      errSL(f'  {node}:', *sorted(names))
    errL(' transitions:')
    for src, d in sorted(self.transitions.items()):
      errSL(f'  {src}:', *sorted(self.matchNames(src)))
      dst_bytes: DefaultDict[int, Set[int]]  = defaultdict(set)
      for byte, dst in d.items():
        dst_bytes[dst].add(byte)
      dst_sorted_bytes = [(dst, sorted(byte_set)) for (dst, byte_set) in dst_bytes.items()]
      for dst, bytes_list in sorted(dst_sorted_bytes, key=lambda p: p[1]):
        byte_ranges = int_tuple_ranges(bytes_list)
        errSL(f'    {codes_desc(byte_ranges)} ==> {dst}', *sorted(self.matchNames(dst)))
    errL()

  def describe_stats(self, label=None) -> None:
    errL(label or type(self).__name__, ':')
    errSL('  match nodes:', len(self.matchNodeNameSets))
    errSL('  nodes:', len(self.transitions))
    errSL('  transitions:', sum(len(d) for d in self.transitions.values()))
    errL()

  def dstNodes(self, node: int) -> FrozenSet[int]:
    return frozenset(self.transitions[node].values())

  def advance(self, state: int, byte: int) -> int:
    return self.transitions[state][byte]

  def match(self, text: str) -> FrozenSet[str]:
    text_bytes = text.encode('utf8')
    state = 0
    for byte in text_bytes:
      try: state = self.advance(state, byte)
      except KeyError: return frozenset()
    return self.matchNames(state)

  def matchNames(self, node: int) -> FrozenSet[str]:
    try: return self.matchNodeNameSets[node]
    except KeyError: return frozenset()

  def matchName(self, node: int) -> Optional[str]:
    try: return first_el(self.matchNodeNameSets[node])
    except KeyError: return None


def minimizeDFA(dfa: DFA) -> DFA:
  '''
  Optimize a DFA by coalescing redundant states.
  sources:
  * http://www.cs.sun.ac.za/rw711/resources/dfa-minimization.pdf.
  * https://en.wikipedia.org/wiki/DFA_minimization.
  * https://www.ics.uci.edu/~eppstein/PADS/PartitionRefinement.py

  Additionally, reduce nodes that match more than one rule where possible,
  or issue errors if not.
  '''

  alphabet = dfa.alphabet
  # start with a rough partition; match nodes are all distinct from each other,
  # and non-match nodes form an additional distinct set.
  init_sets = [{n} for n in dfa.matchNodes] + [set(dfa.nonMatchNodes)]

  sets = { id(s): s for s in init_sets }
  partition = { n: s for s in sets.values() for n in s }

  rev_transitions: DefaultDict[int, DefaultDict[int, Set[int]]] = defaultdict(lambda: defaultdict(set))
  for src, d in dfa.transitions.items():
    for char, dst in d.items():
      rev_transitions[dst][char].add(src)

  def refine(refining_set: Set[int]) -> List[Tuple[Set[int], Set[int]]]:
    '''
    Given refining set B,
    Refine each set A in the partition to a pair of sets: A & B and A - B.
    Return a list of pairs for each changed set;
    one of these is a new set, the other is the mutated original.
    '''
    part_sets_to_intersections: DefaultDict[int, Set[int]] = defaultdict(set)
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

  transitions: DefaultDict[int, Dict[int, int]] = defaultdict(dict)
  for old_node, old_d in dfa.transitions.items():
    new_d = transitions[mapping[old_node]]
    for char, old_dst in old_d.items():
      new_dst = mapping[old_dst]
      try:
        existing = new_d[char]
        if existing != new_dst:
          exit(f'inconsistency in minimized DFA: src state: {old_node}->{new_node}; char: {char!r}; dst state: {old_dst}->{new_dst} != ?->{existing}')
      except KeyError:
        new_d[char] = new_dst

  # Nodes may match more than one rule when the rules overlap.
  # If the set of match nodes for a rule is a superset another rule, ignore it;
  # otherwise intersections are treated as ambiguity errors.

  node_names = { mapping[old] : set(names) for old, names in dfa.matchNodeNameSets.items() }

  name_nodes: DefaultDict[str, Set[int]] = defaultdict(set) # names to sets of nodes.
  for node, names in node_names.items():
    for name in names:
      name_nodes[name].add(node)

  for name, nodes in name_nodes.items():
    for node in tuple(nodes):
      names = node_names[node]
      assert names
      if len(names) == 1: continue # unambiguous.
      for other_name in names:
        if other_name == name: continue
        other_nodes = name_nodes[other_name]
        if other_nodes < nodes: # this rule is a superset of other; it should not match.
          node_names[node].remove(name)
          break

  # check for ambiguous rules.
  ambiguous_name_groups = { tuple(sorted(names)) for names in node_names.values() if len(names) != 1 }
  if ambiguous_name_groups:
    for group in sorted(ambiguous_name_groups):
      errL('Rules are ambiguous: ', ', '.join(group), '.')
    exit(1)

  matchNodeNameSets = { node : frozenset(names) for node, names in node_names.items() }
  return DFA(transitions=dict(transitions), matchNodeNameSets=matchNodeNameSets, literalRules=dfa.literalRules)

