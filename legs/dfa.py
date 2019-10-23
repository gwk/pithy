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
from itertools import chain, combinations
from typing import DefaultDict, Dict, FrozenSet, Iterable, Iterator, List, Optional, Set, Tuple, cast

from pithy.graph import visit_nodes
from pithy.io import errD, errL, errSL
from pithy.iterable import first_el, frozenset_from, int_tuple_ranges, set_from
from pithy.string import prepend_to_nonempty
from pithy.unicode.codepoints import codes_desc


DfaState = int
DfaStateTransitions = Dict[int, DfaState]
DfaTransitions = Dict[int, DfaStateTransitions]

FrozenSetStr0:FrozenSet[str] = frozenset()


class DFA:
  'Deterministic Finite Automaton.'

  def __init__(self, name:str, transitions:DfaTransitions, match_node_kind_sets:Dict[int,FrozenSet[str]], lit_pattern_names:Set[str],
   backtracking_order:Tuple[str,...]=()) -> None:
    assert name
    self.name = name
    self.transitions = transitions
    self.match_node_kind_sets = match_node_kind_sets
    self.lit_pattern_names = lit_pattern_names
    self.backtracking_order = backtracking_order # The best-effort ordering backtracking regex patterns.
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
    return frozenset_from(d.keys() for d in self.all_byte_to_state_dicts)

  @property
  def all_src_nodes(self) -> FrozenSet[int]: return frozenset(self.transitions.keys())

  @property
  def all_dst_nodes(self) -> FrozenSet[int]:
    return frozenset_from(self.dst_nodes(node) for node in self.all_src_nodes)

  @property
  def all_nodes(self) -> FrozenSet[int]: return self.all_src_nodes | self.all_dst_nodes

  @property
  def terminal_nodes(self) -> FrozenSet[int]: return frozenset(n for n in self.all_nodes if not self.transitions.get(n))

  @property
  def match_nodes(self) -> FrozenSet[int]: return frozenset(self.match_node_kind_sets.keys())

  @property
  def non_match_nodes(self) -> FrozenSet[int]: return self.all_nodes - self.match_nodes

  @property
  def partitioned_match_nodes(self) -> Iterable[FrozenSet[int]]:
    # Keyed by (set of match kinds, set of transitions).
    K = Tuple[FrozenSet[str], FrozenSet[Tuple[int,int]]]
    parts = DefaultDict[K,Set[int]](set)
    for node, kind_sets in self.match_node_kind_sets.items():
      k = (kind_sets, frozenset(self.transitions[node].items()))
      parts[k].add(node)
    return (frozenset(s) for s in parts.values())

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
  def pattern_kinds(self) -> FrozenSet[str]: return frozenset_from(self.match_node_kind_sets.values())

  def transition_descs(self) -> Iterator[Tuple[int,List[Tuple[int,str]]]]:
    'Yield (src, [(dst, ranges_desc)]) tuples.'
    for src, d in sorted(self.transitions.items()):
      dst_bytes = DefaultDict[int,Set[int]](set)
      for byte, dst in d.items():
        dst_bytes[dst].add(byte)
      dst_sorted_bytes = [(dst, sorted(byte_set)) for (dst, byte_set) in dst_bytes.items()]
      pairs = []
      for dst, bytes_list in sorted(dst_sorted_bytes, key=lambda p: p[1]):
        byte_ranges = int_tuple_ranges(bytes_list)
        pairs.append((dst, codes_desc(byte_ranges)))
      yield (src, pairs)

  def describe(self, label='') -> None:
    errL(self.name, (label and f': {label}'), ':')
    errL(f' start_node:{self.start_node} end_node:{self.end_node}')
    errL(' match_node_kind_sets:')
    for node, kinds in sorted(self.match_node_kind_sets.items()):
      errSL(f'  {node}:', *sorted(kinds))
    errL(' transitions:')
    for src, pairs in self.transition_descs():
      errSL(f'  {src}:', *sorted(self.match_kinds(src)))
      for dst, ranges_desc in pairs:
        errSL(f'    {ranges_desc} ==> {dst}', *sorted(self.match_kinds(dst)))
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

  Additionally, for nodes that match more than one pattern,
  disambiguate by choosing the most specific node if it exists, or else issue errors.
  '''

  alphabet = dfa.alphabet
  # start with a rough partition. Non-match nodes form one set.
  # Match nodes are mostly distinct from each other, but can be coalesced in some cases.
  init_sets = [set(dfa.non_match_nodes), *dfa.partitioned_match_nodes]

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
    set_pairs:List[Tuple[Set[int],Set[int]]] = []
    for id_part, intersection in part_id_intersections.items():
      part = part_ids_to_parts[id_part]
      if intersection != part: # Split part into difference and intersection.
        part_ids_to_parts[id(intersection)] = intersection
        for x in intersection:
          node_parts[x] = intersection
        part -= intersection # Original part mutates to become difference.
        set_pairs.append((intersection, part)) # type: ignore
    return set_pairs

  # Refinement.
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

  # Map old nodes to new nodes.
  mapping:Dict[int,int] = {}
  for new_node, part in enumerate(sorted(sorted(p) for p in part_ids_to_parts.values()), start_node):
    for old_node in part:
      assert old_node not in mapping, old_node
      mapping[old_node] = new_node

  # Build new transitions.
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
  # If the set of match nodes for one pattern is a superset of another pattern, only match the subset pattern.
  # The typical case is a set of literal keywords plus a more general "identifier" pattern.
  # Other intersections are treated as ambiguity errors.

  # Keep an immutable copy of the full node sets before reduction.
  full_match_node_kinds = { mapping[old] : kinds for old, kinds in dfa.match_node_kind_sets.items() }

  # Create a mutable copy for reduction.
  match_node_kinds = { node : set(kinds) for node, kinds in full_match_node_kinds.items() }

  # Build kind to match nodes map. This does not get reduced.
  kind_match_nodes:DefaultDict[str, Set[int]] = defaultdict(set) # kinds to sets of nodes.
  for node, kinds in match_node_kinds.items():
    for kind in kinds:
      kind_match_nodes[kind].add(node)

  # Reduce ambiguities.
  # For each kind, for each match node, compare this kind to all other kinds matching at this node.
  # If this kind's match set is a strict superset of others, then remove it from the match set *of that node*.
  for kind, nodes in kind_match_nodes.items():
    for node in tuple(nodes): # Convert to tuple for order stability.
      kinds = match_node_kinds[node] # Mutable set.
      assert kinds
      for other_kind in tuple(kinds): # Convert to tuple for order stability.
        if other_kind == kind: continue
        other_nodes = kind_match_nodes[other_kind]
        if other_nodes < nodes: # This pattern is a superset; it should not match.
          try: kinds.remove(kind) # Remove this pattern.
          except KeyError: pass # Already removed.
          # Note: do not update kind_match_nodes as the match sets shrink, or else the subset comparison will start to fail.

  # Check for ambiguous patterns. This must happen after the ambiguity reduction above.
  ambiguous_kind_groups = { tuple(sorted(kinds)) for kinds in match_node_kinds.values() if len(kinds) != 1 }
  if ambiguous_kind_groups:
    for group in sorted(ambiguous_kind_groups):
      errL('Rules are ambiguous: ', ', '.join(group), '.')
    exit(1)


  # Attempt to order the patterns for backtracking regex generation using the full match node sets.
  backtracking_order = calc_backtrack_order(dfa.name, match_node_kinds, kind_match_nodes, transitions)

  # Freeze the reduced match sets.
  match_node_kind_sets = { node : frozenset(kinds) for node, kinds in match_node_kinds.items() }

  return DFA(name=dfa.name, transitions=transitions, match_node_kind_sets=match_node_kind_sets,
    lit_pattern_names=dfa.lit_pattern_names, backtracking_order=backtracking_order)


def calc_backtrack_order(name:str, match_node_kinds:Dict[int,Set[str]], kind_match_nodes:Dict[str,Set[int]],
 transitions:DfaTransitions) -> Tuple[str,...]:
  '''
  Calculate a reasonable order for backtracking regex outputs.
  It is not always possible to generate a correct order,
  because backtracking regex engines handle ambiguity by ordered choice,
  so ambiguity can only addressed with positive or negative assertions ("\\b" is the most common case).
  For example, a keyword literal 'kw' and a name pattern '$Ascii_Letter+' can be fixed by writing "kw\\b" first.
  There are pathological examples that get much worse however.

  The goal is to generate TextMate grammars, so we make a best effort that is not guaranteed to be correct.
  '''

  kind_subset_kinds:DefaultDict[str,Set[str]] = defaultdict(set)
  #^ For each kind, the set of kinds whose match node sets are subsets.

  kind_reachable_kinds:Dict[str,Set[str]] = {}
  #^ For each kind, the set of kinds whose match nodes are reachable from this kind's match nodes.

  for kind, nodes in kind_match_nodes.items():
    if kind == 'invalid': continue # Omit invalid entirely; it is handled separately.
    # Compute subsets.
    other_kinds = set_from(match_node_kinds[node] for node in nodes)
    assert other_kinds
    for other_kind in tuple(other_kinds): # Convert to tuple for order stability.
      if other_kind == kind: continue
      other_nodes = kind_match_nodes[other_kind]
      if other_nodes.issubset(nodes):
        kind_subset_kinds[kind].add(other_kind)
    # Compute reachability.
    next_nodes = set_from(transitions[node].values() for node in nodes)
    reachable_nodes = visit_nodes(start_nodes=next_nodes, visitor=lambda node:transitions[node].values())
    reachable_kinds:Set[str] = set()
    for node in reachable_nodes:
      try: node_kinds = match_node_kinds[node]
      except KeyError: continue
      reachable_kinds.update(node_kinds)
    reachable_kinds.discard(kind)
    kind_reachable_kinds[kind] = reachable_kinds

  kinds = sorted(k for k in kind_match_nodes if k != 'invalid')
  unorderable_kinds:Set[str] = set()
  unorderable_pairs:List[Tuple[str,str]] = []
  for p in combinations(kinds, 2):
    l, r = p
    if l in kind_reachable_kinds[r] and r in kind_reachable_kinds[l]: # Cyclical reachability.
      unorderable_kinds.update(p)
      unorderable_pairs.append(cast(Tuple[str,str], p))

  if unorderable_pairs:
    errL(f'note: `{name}`: patterns cannot be correctly ordered for backtracking regex engines: ',
      ', '.join(str(p) for p in unorderable_pairs), '.')

  def order_key(kind:str) -> Tuple:
    '''
    The ordering heuristic attempts to accommodate the following cases:
    * For cyclical patterns, subset patterns should come first. These require additional assertions. e.g. 'kw' and '\w+'.
    * Otherwise, longer (reachable) patterns should come first to utilize the backtracker, e.g. '==' before '='.
    We choose to place unorderable patterns first because they require attention.
    '''
    orderable = kind not in unorderable_kinds # Unordereables first.
    subsets = sorted(kind_subset_kinds[kind])
    reachables = sorted(kind_reachable_kinds[kind])
    return (orderable, subsets, reachables)

  ordered_kinds = tuple(sorted(kinds, key=order_key))

  return ordered_kinds
