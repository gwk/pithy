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
* match_node_name_sets: dictionary of nodes mapping matching nodes to the set of corresponding pattern names.

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

  def __init__(self, name:str, transitions:DfaTransitions, match_node_name_sets:Dict[int,FrozenSet[str]], lit_patterns:Set[str],
   iso_kinds=FrozenSetStr0, strict_sub_kinds=FrozenSetStr0, strict_sup_kinds=FrozenSetStr0, po_kinds=FrozenSetStr0) -> None:
    assert name
    self.name = name
    self.transitions = transitions
    self.match_node_name_sets = match_node_name_sets
    self.lit_patterns = lit_patterns
    self.iso_kinds = iso_kinds
    self.strict_sub_kinds = strict_sub_kinds
    self.strict_sup_kinds = strict_sup_kinds
    self.po_kinds = po_kinds
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
  def match_nodes(self) -> FrozenSet[int]: return frozenset(self.match_node_name_sets.keys())

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
  def pattern_names(self) -> FrozenSet[str]: return frozenset().union(*self.match_node_name_sets.values()) # type: ignore

  def describe(self, label='') -> None:
    errL(self.name, (label and f': {label}'), ':')
    errL(f' start_node:{self.start_node} end_node:{self.end_node}')
    errL(' match_node_name_sets:')
    for node, names in sorted(self.match_node_name_sets.items()):
      errSL(f'  {node}:', *sorted(names))
    errL(' transitions:')
    for src, d in sorted(self.transitions.items()):
      errSL(f'  {src}:', *sorted(self.match_names(src)))
      dst_bytes:DefaultDict[int, Set[int]]  = defaultdict(set)
      for byte, dst in d.items():
        dst_bytes[dst].add(byte)
      dst_sorted_bytes = [(dst, sorted(byte_set)) for (dst, byte_set) in dst_bytes.items()]
      for dst, bytes_list in sorted(dst_sorted_bytes, key=lambda p: p[1]):
        byte_ranges = int_tuple_ranges(bytes_list)
        errSL(f'    {codes_desc(byte_ranges)} ==> {dst}', *sorted(self.match_names(dst)))
    errL()

  def describe_stats(self, label='') -> None:
    errL(self.name, (label and f': {label}'), ':')
    errSL('  match nodes:', len(self.match_node_name_sets))
    errSL('  nodes:', len(self.transitions))
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
    return self.match_names(state)

  def match_names(self, node:int) -> FrozenSet[str]:
    try: return self.match_node_name_sets[node]
    except KeyError: return frozenset()

  def match_name(self, node:int) -> Optional[str]:
    try: s = self.match_node_name_sets[node]
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
    part_id_intersections:PartIntersections = defaultdict(set)
    for node in refining_set:
      s = node_parts[node]
      part_id_intersections[id(s)].add(node)
    set_pairs = []
    for id_s, intersection in part_id_intersections.items():
      s = part_ids_to_parts[id_s]
      if intersection != s:
        part_ids_to_parts[id(intersection)] = intersection
        for x in intersection:
          node_parts[x] = intersection
        s -= intersection
        set_pairs.append((intersection, s))
    return set_pairs

  remaining = list(init_sets) # distinguishing sets used to refine the partition.
  while remaining:
    s = remaining.pop() # a partition.
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
  # If the set of match nodes for a pattern is a superset of another pattern, ignore it;
  # otherwise intersections are treated as ambiguity errors.

  match_node_names = { mapping[old] : set(names) for old, names in dfa.match_node_name_sets.items() }

  name_match_nodes:DefaultDict[str, Set[int]] = defaultdict(set) # names to sets of nodes.
  for node, names in match_node_names.items():
    for name in names:
      name_match_nodes[name].add(node)

  kind_rels:List[Tuple[str,str]] = [] # (subset, superset) kind pairs.
  for name, nodes in name_match_nodes.items():
    for node in tuple(nodes):
      names = match_node_names[node]
      assert names
      for other_name in tuple(names):
        if other_name == name: continue
        other_nodes = name_match_nodes[other_name]
        if other_nodes < nodes: # this pattern is a superset of other; it should not match.
          kind_rels.append((other_name, name))
          try: names.remove(name)
          except KeyError: pass # Already removed.


  # check for ambiguous patterns.
  ambiguous_name_groups = { tuple(sorted(names)) for names in match_node_names.values() if len(names) != 1 }
  if ambiguous_name_groups:
    for group in sorted(ambiguous_name_groups):
      errL('Rules are ambiguous: ', ', '.join(group), '.')
    exit(1)

  # Determine a satisfactory ordering of kinds.
  sub_kinds_set = { r[0] for r in kind_rels }
  sup_kinds_set = { r[1] for r in kind_rels }

  iso_kinds = [n for n in name_match_nodes if (n not in sub_kinds_set and n not in sup_kinds_set)]
  strict_sub_kinds = {n for n in sub_kinds_set if n not in sup_kinds_set}
  strict_sup_kinds = {n for n in sup_kinds_set if n not in sub_kinds_set}

  po_kinds:List[str] = [] # Partially ordered kinds.
  while kind_rels:
    sub, sup = kind_rels.pop()
    # HACK: For now, just assume we don't get any complex partially ordered kinds.
    assert sub in strict_sub_kinds, sub
    assert sup in strict_sup_kinds, sup

  match_node_name_sets = { node : frozenset(names) for node, names in match_node_names.items() }

  return DFA(name=dfa.name, transitions=transitions, match_node_name_sets=match_node_name_sets, lit_patterns=dfa.lit_patterns,
    iso_kinds=iso_kinds, strict_sub_kinds=strict_sub_kinds, strict_sup_kinds=strict_sup_kinds, po_kinds=po_kinds)
