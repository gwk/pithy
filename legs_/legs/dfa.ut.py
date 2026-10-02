# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from legs.dfa import DFA, minimize_dfa
from utest import utest_run, utest_val


@utest_run
def active_splitter_is_stable() -> None:
  # All seven states are reachable and distinguishable. Processing byte 0 splits the active block {2, 5}.
  # Byte 1 must still use both nodes; using only the mutated remainder {5} leaves distinguishable states merged.
  transitions = {
    0: {0: 0, 1: 2},
    1: {0: 4, 1: 2},
    2: {0: 5, 1: 6},
    3: {0: 4, 1: 0},
    4: {0: 3, 1: 3},
    5: {0: 1, 1: 6},
    6: {0: 2, 1: 1},
  }
  match_node_kind_sets = {6: frozenset({'match'})}
  dfa = DFA('mutation', transitions, match_node_kind_sets, set())
  minimized = minimize_dfa(dfa, start_node=0)
  utest_val(transitions, minimized.transitions)
  utest_val(match_node_kind_sets, minimized.match_node_kind_sets)


@utest_run
def sparse_predecessors() -> None:
  # The start node has no incoming transitions; the match node has no outgoing transitions.
  # Nodes 2 and 3 are equivalent even though different bytes reach them.
  dfa = DFA('sparse', {
    0: {0: 2, 1: 1, 255: 3},
    1: {1: 1},
    2: {255: 4},
    3: {255: 4},
    4: {},
  }, {1: frozenset({'invalid'}), 4: frozenset({'match'})}, set())
  minimized = minimize_dfa(dfa, start_node=0)
  utest_val({0: {0: 2, 1: 1, 255: 2}, 1: {1: 1}, 2: {255: 3}, 3: {}}, minimized.transitions)
  utest_val({1: frozenset({'invalid'}), 3: frozenset({'match'})}, minimized.match_node_kind_sets)
