# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import defaultdict
from itertools import count

from pithy.dict import dict_put

from .patterns import LegsPattern, NfaMutableTransitions
from .dfa import DFA
from .nfa import NFA, NfaState, NfaTransitions


def build_nfa(name:str, named_patterns:list[tuple[str, LegsPattern]], encoding:str) -> NFA:
  '''
  Generate an NFA from a set of patterns.
  The NFA can be used to match against an argument string,
  but cannot produce a token stream directly.
  The `invalid` node is unreachable, and reserved for later use by the derived DFA.
  '''

  indexer = iter(count())
  def mk_node() -> int: return next(indexer)

  start = mk_node() # always 0; see build_dfa.
  invalid = mk_node() # always 1; see build_dfa.

  match_node_kinds:dict[int,str] = { invalid: 'invalid' }

  transitions_dd:NfaMutableTransitions = defaultdict(lambda: defaultdict(set))
  for kind, pattern in named_patterns:
    match_node = mk_node()
    pattern.gen_nfa(mk_node, encoding, transitions_dd, start, match_node)
    dict_put(match_node_kinds, match_node, kind)
  lit_pattern_names = { n for n, pattern in named_patterns if pattern.is_literal }

  transitions:NfaTransitions = {
    src: {char: frozenset(dst) for char, dst in d.items() } for src, d in transitions_dd.items() }
  return NFA(name=name, transitions=transitions, match_node_kinds=match_node_kinds, lit_pattern_names=lit_pattern_names)


def build_dfa(nfa:NFA) -> DFA:
  '''
  Build a DFA from an NFA.

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

  nfa_states_to_dfa_nodes = defaultdict[NfaState, int](mk_node)
  start = nfa.advance_empties({0})
  invalid = frozenset({1}) # no need to advance_empties as `invalid` is unreachable in the nfa.
  start_node = nfa_states_to_dfa_nodes[start]
  invalid_node = nfa_states_to_dfa_nodes[invalid]

  transitions = defaultdict[int,dict[int,int]](dict)
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

  # Explicitly add transitions to and from `invalid`, which is otherwise not reachable.
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
  node_kinds = defaultdict[int, set[str]](set) # nodes to sets of kinds.
  for nfa_state, dfa_node in nfa_states_to_dfa_nodes.items():
    for nfa_node in nfa_state:
      try: kind = nfa.match_node_kinds[nfa_node]
      except KeyError: continue
      node_kinds[dfa_node].add(kind)
  match_node_kind_sets = { node : frozenset(kinds) for node, kinds in node_kinds.items() }

  return DFA(name=nfa.name, transitions=dict(transitions), match_node_kind_sets=match_node_kind_sets, lit_pattern_names=nfa.lit_pattern_names)