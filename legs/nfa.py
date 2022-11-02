# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Nondeterministic Finite Automata.
See the documentation in dfa.py for more.

`empty_symbol` is a reserved value (-1 is not part of the byte alphabet)
that represents a nondeterministic jump between NFA nodes.
'''

from collections import defaultdict
from typing import Iterable

from pithy.io import errL, errSL
from pithy.iterable import filtermap_with_mapping, frozenset_from, int_tuple_ranges, set_from
from pithy.string import prepend_to_nonempty
from pithy.unicode.codepoints import codes_desc


NfaState = frozenset[int]
NfaStateTransitions = dict[int, NfaState]
NfaTransitions = dict[int, NfaStateTransitions]


empty_symbol = -1 # not a legitimate byte value.


class NFA:
  'Nondeterministic Finite Automaton.'

  def __init__(self, name:str, transitions:NfaTransitions, match_node_kinds:dict[int, str], lit_pattern_names:set[str]):
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
  def alphabet(self) -> frozenset[int]:
    s = set_from(d.keys() for d in self.all_byte_to_state_dicts)
    s.discard(empty_symbol)
    return frozenset(s)

  @property
  def all_src_nodes(self) -> frozenset[int]: return frozenset(self.transitions.keys())

  @property
  def all_dst_nodes(self) -> frozenset[int]:
    return frozenset_from(self.dst_nodes(node) for node in self.all_src_nodes)

  @property
  def all_nodes(self) -> frozenset[int]: return self.all_src_nodes | self.all_dst_nodes

  @property
  def terminal_nodes(self) -> frozenset[int]: return frozenset(n for n in self.all_nodes if not self.transitions.get(n))

  @property
  def match_nodes(self) -> frozenset[int]: return frozenset(self.match_node_kinds.keys())

  @property
  def non_match_nodes(self) -> frozenset[int]: return self.all_nodes - self.match_nodes

  @property
  def pre_match_nodes(self) -> frozenset[int]:
    if self.is_empty:
      return frozenset() # empty.
    match_nodes = self.match_nodes
    nodes:set[int] = set()
    remaining = {0}
    while remaining:
      node = remaining.pop()
      assert node not in nodes
      if node in match_nodes: continue
      nodes.add(node)
      remaining.update(self.dst_nodes(node) - nodes)
    return frozenset(nodes)

  @property
  def post_match_nodes(self) -> frozenset[int]:
    match_nodes = self.match_nodes
    nodes:set[int] = set()
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
      dst_bytes = defaultdict[frozenset[int], set[int]](set)
      for byte, dst in d.items():
        dst_bytes[dst].add(byte)
      dst_sorted_bytes = [(dst, sorted(byte_set)) for (dst, byte_set) in dst_bytes.items()]
      for dst, bytes_list in sorted(dst_sorted_bytes, key=lambda p: p[1]):
        byte_ranges = int_tuple_ranges(bytes_list)
        errL('    ', codes_desc(byte_ranges), ' ==> ', dst)
    errL()

  def describe_stats(self, label=None) -> None:
    errL(self.name, (label and f': {label}'), ':')
    errSL(f'  match nodes: {len(self.match_node_kinds):_}')
    errSL(f'  nodes: {len(self.transitions):_}')
    errSL(f'  transitions: {sum(len(d) for d in self.transitions.values()):_}')
    errL()

  def dst_nodes(self, node:int) -> frozenset[int]:
    return frozenset_from(self.transitions[node].values())

  def validate(self) -> list[str]:
    start = self.advance_empties({0})
    msgs = []
    for node, kind in sorted(self.match_node_kinds.items()):
      if node in start:
        msgs.append(f'error: pattern is trivially matched from start: {kind}.')
    return msgs

  def advance(self, state:frozenset[int], byte:int) -> NfaState:
    nextState:set[int] = set()
    for node in state:
      try: dst_nodes = self.transitions[node][byte]
      except KeyError: pass
      else: nextState.update(dst_nodes)
    return self.advance_empties(nextState)

  def match(self, text_bytes:bytes) -> frozenset[str]:
    state = self.advance_empties({0})
    #errSL('NFA start:', state)
    for byte in text_bytes:
      state = self.advance(state, byte)
      #errL(f'NFA step: {bytes([byte])} -> {state}')
    s:Iterable[str] = filtermap_with_mapping(state, self.match_node_kinds)
    all_matches:frozenset[str] = frozenset(s)
    literal_matches = frozenset(n for n in all_matches if n in self.lit_pattern_names)
    return literal_matches or all_matches

  def advance_empties(self, mut_state:set[int]) -> NfaState:
    expanded:set[int] = set()
    while mut_state:
      node = mut_state.pop()
      expanded.add(node)
      try: dst_nodes = self.transitions[node][empty_symbol]
      except KeyError: continue
      novel = dst_nodes - expanded
      mut_state.update(novel)
    return frozenset(expanded)
