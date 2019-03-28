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
* match_node_kind_sets: dictionary of nodes mapping matching nodes to the set of corresponding pattern names.

For NFAs, the start state is always {0}, and the invalid state is always {1}.
For DFAs, start_state and invalid_state are the lowest two node indices, and are available as attributes.

For all bytes that do not naturally transition out of `start`,
artificial transitions are added from `start` to `invalid`,
and `invalid` transitions to itself for all bytes that are not a valid transition from `start`.
This trick allows the FA to always progress from the start state,
thus producing a stream of tokens that seamlessly cover any input string.
'''

from collections import defaultdict
from itertools import chain
from typing import DefaultDict, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple, cast

from pithy.graph import visit_nodes
from pithy.io import errL, errSL
from pithy.iterable import first_el, int_tuple_ranges
from pithy.string import prepend_to_nonempty

from .unicode.codepoints import codes_desc


DfaState = int
DfaStateTransitions = Dict[int, DfaState]
DfaTransitions = Dict[int, DfaStateTransitions]

FrozenSetStr0:FrozenSet[str] = frozenset()


class DFA:
  'Deterministic Finite Automaton.'

  def __init__(self, name:str, transitions:DfaTransitions, match_node_kind_sets:Dict[int,FrozenSet[str]], lit_patterns:Set[str],
   kinds_greedy_ordered=Tuple[str,...]) -> None:
    assert name
    self.name = name
    self.transitions = transitions
    self.match_node_kind_sets = match_node_kind_sets
    self.lit_patterns = lit_patterns
    self.kinds_greedy_ordered = kinds_greedy_ordered # The ordering necessary for greedy regex choices to match correctly.
    self.start_node = min(transitions)
    self.invalid_node = self.start_node + 1
    self.end_node = max(transitions) + 1

  @property
  def is_empty(self) -> bool:
    return not self.transitions

  @property
  def all_byte_to_state_dicts(self) -> Iterable[DfaStateTransitions]: return self.transitions.values()

  @property
  def alphabet(self) -> FrozenSet[int]:
    a:Set[int] = set()
    a.update(*(d.keys() for d in self.all_byte_to_state_dicts))
    return cast(FrozenSet[int], frozenset(a)) # mypy bug.

  @property
  def all_src_nodes(self) -> FrozenSet[int]: return frozenset(self.transitions.keys())

  @property
  def all_dst_nodes(self) -> FrozenSet[int]:
    s:Set[int] = set()
    s.update(*(self.dst_nodes(node) for node in self.all_src_nodes))
    return frozenset(s)

  @property
  def all_nodes(self) -> FrozenSet[int]: return self.all_src_nodes | self.all_dst_nodes

  @property
  def terminal_nodes(self) -> FrozenSet[int]: return frozenset(n for n in self.all_nodes if not self.transitions.get(n))

  @property
  def match_nodes(self) -> FrozenSet[int]: return frozenset(self.match_node_kind_sets.keys())

  @property
  def non_match_nodes(self) -> FrozenSet[int]: return self.all_nodes - self.match_nodes

  @property
  def pre_match_nodes(self) -> FrozenSet[int]:
    if self.is_empty:
      return frozenset() # empty.
    match_nodes = self.match_nodes
    nodes:Set[int] = set()
    remaining = {self.start_node}
    while remaining:
      node = remaining.pop()
      assert node not in nodes
      if node in match_nodes: continue
      nodes.add(node)
      remaining.update(self.dst_nodes(node) - nodes)
    return frozenset(nodes)

  @property
  def post_match_nodes(self) -> FrozenSet[int]:
    match_nodes = self.match_nodes
    nodes:Set[int] = set()
    remaining = set(match_nodes)
    while remaining:
      node = remaining.pop()
      for dst in self.dst_nodes(node):
        if dst not in match_nodes and dst not in nodes:
          nodes.add(dst)
          remaining.add(dst)
    return frozenset(nodes)

  @property
  def pattern_kinds(self) -> FrozenSet[str]: return frozenset().union(*self.match_node_kind_sets.values()) # type: ignore

  def describe(self, label='') -> None:
    errL(self.name, (label and f': {label}'), ':')
    errL(f' start_node:{self.start_node} end_node:{self.end_node}')
    errL(' match_node_kind_sets:')
    for node, kinds in sorted(self.match_node_kind_sets.items()):
      errSL(f'  {node}:', *sorted(kinds))
    errL(' transitions:')
    for src, d in sorted(self.transitions.items()):
      errSL(f'  {src}:', *sorted(self.match_kinds(src)))
      dst_bytes:DefaultDict[int, Set[int]]  = defaultdict(set)
      for byte, dst in d.items():
        dst_bytes[dst].add(byte)
      dst_sorted_bytes = [(dst, sorted(byte_set)) for (dst, byte_set) in dst_bytes.items()]
      for dst, bytes_list in sorted(dst_sorted_bytes, key=lambda p: p[1]):
        byte_ranges = int_tuple_ranges(bytes_list)
        errSL(f'    {codes_desc(byte_ranges)} ==> {dst}', *sorted(self.match_kinds(dst)))
    errL()

  def describe_stats(self, label='') -> None:
    errL(self.name, (label and f': {label}'), ':')
    errSL('  nodes:', len(self.transitions))
    errSL('  match nodes:', len(self.match_node_kind_sets))
    errSL('  post-match nodes:', len(self.post_match_nodes))
    errSL('  transitions:', sum(len(d) for d in self.transitions.values()))
    errL()

  def dst_nodes(self, node:int) -> FrozenSet[int]:
    return frozenset(self.transitions[node].values())

  def advance(self, state:int, byte:int) -> int:
    return self.transitions[state][byte]

  def match(self, text:str) -> FrozenSet[str]:
    text_bytes = text.encode('utf8')
    state = self.start_node
    for byte in text_bytes:
      try: state = self.advance(state, byte)
      except KeyError: return frozenset()
    return self.match_kinds(state)

  def match_kinds(self, node:int) -> FrozenSet[str]:
    try: return self.match_node_kind_sets[node]
    except KeyError: return frozenset()

  def match_kind(self, node:int) -> Optional[str]:
    try: s = self.match_node_kind_sets[node]
    except KeyError: return None
    assert len(s) == 1
    return first_el(s)


def minimize_dfa(dfa:DFA, start_node:int) -> DFA:
  '''
  Optimize a DFA by coalescing redundant states.
  sources:
  * http://www.cs.sun.ac.za/rw711/resources/dfa-minimization.pdf.
  * https://en.wikipedia.org/wiki/DFA_minimization.
  * https://www.ics.uci.edu/~eppstein/PADS/PartitionRefinement.py

  Additionally, reduce nodes that match more than one pattern where possible,
  or issue errors if not.
  '''

  alphabet = dfa.alphabet
  # start with a rough partition; non-match nodes form one set,
  # and each match node is distinct from all others.
  init_sets = [set(dfa.non_match_nodes), *({n} for n in dfa.match_nodes)]

  part_ids_to_parts = { id(s): s for s in init_sets }
  node_parts = { n: s for s in part_ids_to_parts.values() for n in s }

  rev_transitions:DefaultDict[int, DefaultDict[int, Set[int]]] = defaultdict(lambda: defaultdict(set))
  for src, d in dfa.transitions.items():
    for char, dst in d.items():
      rev_transitions[dst][char].add(src)

  def validate_partition() -> None:
    for node, part in node_parts.items():
      assert node in part, (node, part)
    parts = list(part_ids_to_parts.values())
    for i, pr in enumerate(parts):
      for j in range(i):
        pl = parts[j]
        assert pl.isdisjoint(pr), (pl, pr)

  PartIntersections = DefaultDict[int, Set[int]] # Optimization: types in hot functions can waste time.
  def refine(refining_set:Set[int]) -> List[Tuple[Set[int], Set[int]]]:
    '''
    Given refining set B, refine each set A in the partition to a pair of sets: A & B and A - B.
    Return a list of pairs for each changed set;
    one of these is a new set, the other is the mutated original.
    '''
    # Accumulate intersection sets.
    part_id_intersections:PartIntersections = defaultdict(set)
    for node in refining_set:
      part = node_parts[node]
      part_id_intersections[id(part)].add(node)
    # Split existing sets by the intersection sets.
    set_pairs = []
    for id_part, intersection in part_id_intersections.items():
      part = part_ids_to_parts[id_part]
      if intersection != part: # Split part into difference and intersection.
        part_ids_to_parts[id(intersection)] = intersection
        for x in intersection:
          node_parts[x] = intersection
        part -= intersection # Original part mutates to become difference.
        set_pairs.append((intersection, part))
    return set_pairs

  remaining = list(init_sets) # distinguishing sets used to refine the partition.
  while remaining:
    s = remaining.pop() # a partition.
    # Note: there seems to be a possible risk of incorrectness here:
    # `s` is one of the partitions, and can be mutated by refine as we iterate over the alphabet.
    # Are we sure that this is ok?
    for char in alphabet:
      # Find all nodes `m` that transition via `char` to any node `n` in `s`.
      dsts = set(chain.from_iterable(rev_transitions[node][char] for node in s))
      #dsts_brute = [node for node in node_parts if dfa.transitions[node].get(char) in s] # brute force version is slow.
      #assert set(dsts_brute) == dsts
      if not dsts: continue # no refinement.
      for a, b in refine(dsts):
        if len(a) < len(b): # Prefer the smaller set to continue refining with.
          if a not in remaining: remaining.append(a)
          elif b not in remaining: remaining.append(b)
        else:
          if b not in remaining: remaining.append(b)
          elif a not in remaining: remaining.append(a)

  validate_partition()

  mapping:Dict[int,int] = {}
  for new_node, part in enumerate(sorted(sorted(p) for p in part_ids_to_parts.values()), start_node):
    for old_node in part:
      assert old_node not in mapping, old_node
      mapping[old_node] = new_node

  transitions_dd:DefaultDict[int,Dict[int,int]] = defaultdict(dict)
  for old_node, old_d in dfa.transitions.items():
    new_d = transitions_dd[mapping[old_node]]
    for char, old_dst in old_d.items():
      new_dst = mapping[old_dst]
      try:
        existing = new_d[char]
        if existing != new_dst:
          exit('inconsistency in minimized DFA:\n'
            f'src state: {old_node}->{new_node}; char: {char!r};\n'
            f'dst state: {old_dst}->{new_dst} != ?->{existing}')
      except KeyError:
        new_d[char] = new_dst

  transitions = dict(transitions_dd)

  # Nodes may match more than one pattern when the patterns overlap.
  # If the set of match nodes for one pattern is a superset of another pattern, only match the subset pattern;
  # a typical case is a set of literal keywords plus a more general "identifier" pattern.
  # Other intersections are treated as ambiguity errors.

  match_node_kinds = { mapping[old] : set(kinds) for old, kinds in dfa.match_node_kind_sets.items() }

  kind_match_nodes:DefaultDict[str, Set[int]] = defaultdict(set) # kinds to sets of nodes.
  for node, kinds in match_node_kinds.items():
    for kind in kinds:
      kind_match_nodes[kind].add(node)

  kind_rels:DefaultDict[str,Set[str]] = defaultdict(set)
  #^ For each kind, the set of nodes that must precede this node in generated regex choices.
  for kind, nodes in kind_match_nodes.items():
    for node in tuple(nodes):
      kinds = match_node_kinds[node]
      assert kinds
      for other_kind in tuple(kinds):
        if other_kind == kind: continue
        other_nodes = kind_match_nodes[other_kind]
        if other_nodes < nodes: # This pattern is a superset; it should not match.
          kind_rels[kind].add(other_kind) # Other pattern is more specific, must be tried first.
          try: kinds.remove(kind)
          except KeyError: pass # Already removed.

  # Check for ambiguous patterns.
  ambiguous_kind_groups = { tuple(sorted(kinds)) for kinds in match_node_kinds.values() if len(kinds) != 1 }
  if ambiguous_kind_groups:
    for group in sorted(ambiguous_kind_groups):
      errL('Rules are ambiguous: ', ', '.join(group), '.')
    exit(1)

  # Determine a satisfactory ordering of kinds for generated greedy regex choices.
  # `kind_rels` is currently half complete: it will prefer more specific patterns over less specific ones.
  # However it must also prefer longer patterns over shorter ones.
  # This is probably still not adequate for some cases.
  for kind, nodes in kind_match_nodes.items():
    reachable_nodes = visit_nodes(start_nodes=nodes, visitor=lambda node:transitions[node].values())
    reachable_kinds = set()
    for node in reachable_nodes:
      try: node_kinds = match_node_kinds[node]
      except KeyError: continue
      reachable_kinds.update(node_kinds)
    reachable_kinds.discard(kind)
    kind_rels[kind].update(reachable_kinds) # Reachable kinds must precede this kind.

  ordered_kinds = sorted((sorted(supers), kind) for kind, supers in kind_rels.items())
  unorderable_pairs:List[Tuple[str,str]] = []
  for supers, kind in ordered_kinds:
    for sup in supers:
      if kind < sup and kind in kind_rels[sup]:
        unorderable_pairs.append((kind, sup))

  if unorderable_pairs:
    errL(f'note: `{dfa.name}`: minimized DFA contains patterns that cannot be correctly ordered for greedy regex choice: ',
      ', '.join(str(p) for p in unorderable_pairs), '.')

  kinds_greedy_ordered = tuple(kind for _, kind in ordered_kinds)

  match_node_kind_sets = { node : frozenset(kinds) for node, kinds in match_node_kinds.items() }

  return DFA(name=dfa.name, transitions=transitions, match_node_kind_sets=match_node_kind_sets,
    lit_patterns=dfa.lit_patterns, kinds_greedy_ordered=kinds_greedy_ordered)
