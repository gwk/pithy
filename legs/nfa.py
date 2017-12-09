# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Nondeterministic Finite Automata.
See the documentation in dfa.py for more.

`empty_symbol` is a reserved value (-1 is not part of the byte alphabet)
that represents a nondeterministic jump between NFA nodes.
'''

from collections import defaultdict
from itertools import count
from typing import *

from pithy.io import errL, errSL
from pithy.iterable import filtermap_with_mapping, int_tuple_ranges
from pithy.string_utils import prepend_to_nonempty

from .codepoints import codes_desc
from .dfa import DFA


NfaState = FrozenSet[int]
NfaStateTransitions = Dict[int, NfaState]
NfaTransitions = Dict[int, NfaStateTransitions]


empty_symbol = -1 # not a legitimate byte value.


class NFA:
  'Nondeterministic Finite Automaton.'

  def __init__(self, transitions: NfaTransitions, matchNodeNames: Dict[int, str], literalRules: Set[str]) -> None:
    self.transitions = transitions
    self.matchNodeNames = matchNodeNames
    self.literalRules = literalRules


  @property
  def isEmpty(self) -> bool:
    return not self.transitions

  @property
  def allByteToStateDicts(self) -> Iterable[NfaStateTransitions]: return self.transitions.values()

  @property
  def alphabet(self) -> FrozenSet[int]:
    s: Set[int] = set()
    s.update(*(d.keys() for d in self.allByteToStateDicts))
    s.discard(empty_symbol)
    return frozenset(s)

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
  def matchNodes(self) -> FrozenSet[int]: return frozenset(self.matchNodeNames.keys())

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

  def describe(self, label=None) -> None:
    errL(label or type(self).__name__, ':')
    errL(' matchNodeNames:')
    for node, name in sorted(self.matchNodeNames.items()):
      errL(f'  {node}: {name}')
    errL(' transitions:')
    for src, d in sorted(self.transitions.items()):
      errL(f'  {src}:{prepend_to_nonempty(" ", self.matchNodeNames.get(src, ""))}')
      dst_bytes: DefaultDict[FrozenSet[int], Set[int]] = defaultdict(set)
      for byte, dst in d.items():
        dst_bytes[dst].add(byte)
      dst_sorted_bytes = [(dst, sorted(byte_set)) for (dst, byte_set) in dst_bytes.items()]
      for dst, bytes_list in sorted(dst_sorted_bytes, key=lambda p: p[1]):
        byte_ranges = int_tuple_ranges(bytes_list)
        errL('    ', codes_desc(byte_ranges), ' ==> ', dst)
    errL()

  def describe_stats(self, label=None) -> None:
    errL(label or type(self).__name__, ':')
    errSL('  match nodes:', len(self.matchNodeNames))
    errSL('  nodes:', len(self.transitions))
    errSL('  transitions:', sum(len(d) for d in self.transitions.values()))
    errL()

  def dstNodes(self, node: int) -> FrozenSet[int]:
    s: Set[int] = set()
    s.update(*self.transitions[node].values())
    return FrozenSet(s)

  def validate(self) -> List[str]:
    start = self.advanceEmpties(frozenset({0}))
    msgs = []
    for node, name in sorted(self.matchNodeNames.items()):
      if node in start:
        msgs.append('error: rule is trivially matched from start: {}.'.format(name))
    return msgs

  def advance(self, state: FrozenSet[int], byte: int) -> NfaState:
    nextState: Set[int] = set()
    for node in state:
      try: dstNodes = self.transitions[node][byte]
      except KeyError: pass
      else: nextState.update(dstNodes)
    return self.advanceEmpties(frozenset(nextState))

  def match(self, text: Union[str, bytes], start_state: NfaState=frozenset({0})) -> FrozenSet[str]:
    if isinstance(text, str):
      text = text.encode()
    state = self.advanceEmpties(start_state)
    #errSL('NFA start_state:', state)
    for byte in text:
      state = self.advance(state, byte)
      #errL(f'NFA step: {bytes([byte])} -> {state}')
    s: Iterable[str] = filtermap_with_mapping(state, self.matchNodeNames)
    all_matches: FrozenSet[str] = frozenset(s)
    literal_matches = frozenset(n for n in all_matches if n in self.literalRules)
    return literal_matches or all_matches

  def advanceEmpties(self, state: NfaState) -> NfaState:
    remaining = set(state)
    expanded: Set[int] = set()
    while remaining:
      node = remaining.pop()
      expanded.add(node)
      try: dstNodes = self.transitions[node][empty_symbol]
      except KeyError: continue
      novel = dstNodes - expanded
      remaining.update(novel)
    return frozenset(expanded)



def genDFA(nfa: NFA) -> DFA:
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
  the generated lexer explicitly defaults into the invalid state.
  '''

  indexer = iter(count())
  def mk_node() -> int: return next(indexer)

  nfa_states_to_dfa_nodes: DefaultDict[NfaState, int] = defaultdict(mk_node)
  start = frozenset(nfa.advanceEmpties(frozenset({0})))
  invalid = frozenset({1}) # no need to advanceEmpties as `invalid` is unreachable in the nfa.
  start_node = nfa_states_to_dfa_nodes[start]
  invalid_node = nfa_states_to_dfa_nodes[invalid]

  transitions: DefaultDict[int, Dict[int, int]] = defaultdict(dict)
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

  # Generate matchNodeNameSets.
  node_names: DefaultDict[int, Set[str]] = defaultdict(set) # nodes to sets of names.
  for nfa_state, dfa_node in nfa_states_to_dfa_nodes.items():
    for nfa_node in nfa_state:
      try: name = nfa.matchNodeNames[nfa_node]
      except KeyError: continue
      node_names[dfa_node].add(name)
  matchNodeNameSets = { node : frozenset(names) for node, names in node_names.items() }

  return DFA(transitions=dict(transitions), matchNodeNameSets=matchNodeNameSets, literalRules=nfa.literalRules)


