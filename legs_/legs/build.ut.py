# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from legs.build import build_dfa
from legs.nfa import empty_symbol, NFA
from utest import utest, utest_run, utest_val


@utest_run
def consuming_transitions_and_epsilon_closures() -> None:
  # Epsilon cycles occur before and after 'a'; its two destinations must both contribute outgoing transitions.
  # Nodes 8 and 9 have no outgoing transition entries. Node 7 reaches the 'ab' match by an epsilon transition.
  nfa = NFA('closures', 'utf-8', {
    0: {empty_symbol: frozenset({2})},
    2: {empty_symbol: frozenset({0}), ord('a'): frozenset({3, 4})},
    3: {empty_symbol: frozenset({5})},
    4: {empty_symbol: frozenset({6})},
    5: {empty_symbol: frozenset({3}), ord('b'): frozenset({7})},
    6: {ord('c'): frozenset({8})},
    7: {empty_symbol: frozenset({9})},
  }, {1: 'invalid', 8: 'ac', 9: 'ab'}, set())
  dfa = build_dfa(nfa)
  utest(frozenset({'ab'}), dfa.match, b'ab')
  utest(frozenset({'ac'}), dfa.match, b'ac')
  for text in (b'', b'a', b'aa', b'ad', b'aba'):
    utest(frozenset(), dfa.match, text)
  utest(frozenset({'invalid'}), dfa.match, b'z')
  utest_val(False, empty_symbol in dfa.alphabet)
