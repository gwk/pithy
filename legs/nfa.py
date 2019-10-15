# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Nondeterministic Finite Automata.
See the documentation in dfa.py for more.

`empty_symbol` is a reserved value (-1 is not part of the byte alphabet)
that represents a nondeterministic jump between NFA nodes.
'''

from collections import defaultdict
from itertools import count
from typing import DefaultDict, Dict, FrozenSet, Iterable, List, Set

from pithy.io import errL, errSL
from pithy.iterable import frozenset_from, filtermap_with_mapping, int_tuple_ranges, set_from
from pithy.string import prepend_to_nonempty
from pithy.unicode.codepoints import codes_desc

from .dfa import DFA


NfaState = FrozenSet[int]
NfaStateTransitions = Dict[int, NfaState]
NfaTransitions = Dict[int, NfaStateTransitions]


empty_symbol = -1 # not a legitimate byte value.


class NFA:
  'Nondeterministic Finite Automaton.'

  def __init__(self, name:str, transitions:NfaTransitions, match_node_kinds:Dict[int, str], lit_pattern_names:Set[str]) -> None:
    assert name
    self.name = name
    self.transitions = transitions
    self.match_node_kinds = match_node_kinds
    self.lit_pattern_names = lit_pattern_names


  @property
  def is_empty(self) -> bool:
    return not self.transitions

  @property
  def all_byte_to_state_dicts(self) -> Iterable[NfaStateTransitions]: return self.transitions.values()

  @property
  def alphabet(self) -> FrozenSet[int]:
    s = set_from(d.keys() for d in self.all_byte_to_state_dicts)
    s.discard(empty_symbol)
    return frozenset(s)

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
  def match_nodes(self) -> FrozenSet[int]: return frozenset(self.match_node_kinds.keys())

  @property
  def non_match_nodes(self) -> FrozenSet[int]: return self.all_nodes - self.match_nodes

  @property
  def pre_match_nodes(self) -> FrozenSet[int]:
    if self.is_empty:
      return frozenset() # empty.
    match_nodes = self.match_nodes
    nodes:Set[int] = set()
    remaining = {0}
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

  def describe(self, label=None) -> None:
    errL(self.name, (label and f': {label}'), ':')
    errL(' match_node_kinds:')
    for node, kind in sorted(self.match_node_kinds.items()):
      errL(f'  {node}: {kind}')
    errL(' transitions:')
    for src, d in sorted(self.transitions.items()):
      errL(f'  {src}:{prepend_to_nonempty(" ", self.match_node_kinds.get(src, ""))}')
      dst_bytes:DefaultDict[FrozenSet[int], Set[int]] = defaultdict(set)
      for byte, dst in d.items():
        dst_bytes[dst].add(byte)
      dst_sorted_bytes = [(dst, sorted(byte_set)) for (dst, byte_set) in dst_bytes.items()]
      for dst, bytes_list in sorted(dst_sorted_bytes, key=lambda p: p[1]):
        byte_ranges = int_tuple_ranges(bytes_list)
        errL('    ', codes_desc(byte_ranges), ' ==> ', dst)
    errL()

  def describe_stats(self, label=None) -> None:
    errL(self.name, (label and f': {label}'), ':')
    errSL('  match nodes:', len(self.match_node_kinds))
    errSL('  nodes:', len(self.transitions))
    errSL('  transitions:', sum(len(d) for d in self.transitions.values()))
    errL()

  def dst_nodes(self, node:int) -> FrozenSet[int]:
    return frozenset_from(self.transitions[node].values())

  def validate(self) -> List[str]:
    start = self.advance_empties({0})
    msgs = []
    for node, kind in sorted(self.match_node_kinds.items()):
      if node in start:
        msgs.append(f'error: pattern is trivially matched from start: {kind}.')
    return msgs

  def advance(self, state:FrozenSet[int], byte:int) -> NfaState:
    nextState:Set[int] = set()
    for node in state:
      try: dst_nodes = self.transitions[node][byte]
      except KeyError: pass
      else: nextState.update(dst_nodes)
    return self.advance_empties(nextState)

  def match(self, text:str) -> FrozenSet[str]:
    text_bytes = text.encode('utf8')
    state = self.advance_empties({0})
    #errSL('NFA start:', state)
    for byte in text_bytes:
      state = self.advance(state, byte)
      #errL(f'NFA step: {bytes([byte])} -> {state}')
    s:Iterable[str] = filtermap_with_mapping(state, self.match_node_kinds)
    all_matches:FrozenSet[str] = frozenset(s)
    literal_matches = frozenset(n for n in all_matches if n in self.lit_pattern_names)
    return literal_matches or all_matches

  def advance_empties(self, mut_state:Set[int]) -> NfaState:
    expanded:Set[int] = set()
    while mut_state:
      node = mut_state.pop()
      expanded.add(node)
      try: dst_nodes = self.transitions[node][empty_symbol]
      except KeyError: continue
      novel = dst_nodes - expanded
      mut_state.update(novel)
    return frozenset(expanded)



def gen_dfa(nfa:NFA) -> DFA:
  '''
  Generate a DFA from an NFA.

  Conceptually, a DFA node is equivalent to a set of NFA nodes.
  Note that this is easily confused with an NFA state (also a set of NFA nodes).
  A DFA has a node for every reachable subset of nodes in the corresponding NFA.
  In the worst case, there will be an exponential increase in number of nodes.

  Unlike the NFA, the DFA's operational state is just a single node value.

  For each DFA node, there is a mapping from byte values to destination nodes.
  Conceputally, generating a lexer from a DFA is straightforward:
  switch on the current state, and then switch on the current byte.
  '''

  indexer = iter(count())
  def mk_node() -> int: return next(indexer)

  nfa_states_to_dfa_nodes:DefaultDict[NfaState, int] = defaultdict(mk_node)
  start = nfa.advance_empties({0})
  invalid = frozenset({1}) # no need to advance_empties as `invalid` is unreachable in the nfa.
  start_node = nfa_states_to_dfa_nodes[start]
  invalid_node = nfa_states_to_dfa_nodes[invalid]

  transitions:DefaultDict[int,Dict[int,int]] = defaultdict(dict)
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

  # explicitly add transitions to and from `invalid`, which is otherwise not reachable.
  # `start` transitions to `invalid` for all bytes not yet covered.
  # `invalid` transitions to itself for those same bytes.
  assert invalid_node not in transitions
  start_dict = transitions[start_node]
  invalid_dict = transitions[invalid_node]
  invalid_start_chars = set(range(0x100)) - set(start_dict)
  for c in invalid_start_chars:
    start_dict[c] = invalid_node
    invalid_dict[c] = invalid_node

  # Generate match_node_kind_sets.
  node_kinds:DefaultDict[int, Set[str]] = defaultdict(set) # nodes to sets of kinds.
  for nfa_state, dfa_node in nfa_states_to_dfa_nodes.items():
    for nfa_node in nfa_state:
      try: kind = nfa.match_node_kinds[nfa_node]
      except KeyError: continue
      node_kinds[dfa_node].add(kind)
  match_node_kind_sets = { node : frozenset(kinds) for node, kinds in node_kinds.items() }

  return DFA(name=nfa.name, transitions=dict(transitions), match_node_kind_sets=match_node_kind_sets, lit_pattern_names=nfa.lit_pattern_names)


