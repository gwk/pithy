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
