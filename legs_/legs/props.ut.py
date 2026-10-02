# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from legs.parse import parse_legs
from legs.props import dfa_coverage_inputs, GrammarChecker, nfa_longest_match, PropertyError
from utest import utest, utest_exc, utest_seq, utest_val


grammar_text = '''
# Patterns
spaces: \\s+
word: $Ascii_Letter+
if
num: $Ascii_Number+ (. $Ascii_Number+)?
paren_o: \\(
paren_c: \\)
lower: $Ll+

# Modes
main: spaces word if num paren_o paren_c
inner: spaces num paren_o paren_c lower

# Transitions
main : paren_o :: inner : paren_c
inner : paren_o :: inner : paren_c
'''

grammar = parse_legs('test', grammar_text)
checker = GrammarChecker(grammar)


# The NFA oracle.
main_nfa = checker.automata['main'].nfa
utest((2, frozenset({'word'})), nfa_longest_match, main_nfa, b'ab 1', 0)
utest((2, frozenset({'if', 'word'})), nfa_longest_match, main_nfa, b'if', 0)
utest((1, frozenset({'num'})), nfa_longest_match, main_nfa, b'1.x', 0) # The match is not extended by the incomplete fraction.
utest((0, frozenset()), nfa_longest_match, main_nfa, b'!', 0)

# Individual inputs.
utest(None, checker.check_tokens, b'if x (1.5 (2) \xc3\xa9) 3.', 'main')
utest(None, checker.check_tokens, b'\xff!\xc3', 'inner')
utest(None, checker.check_single_token, b'12.5', 'main', 'num')
utest(None, checker.check_single_token, b'if', 'main', 'word') # The token kind is `if`, but the text also matches `word`.
utest_exc(PropertyError, checker.check_single_token, b'12.', 'main', 'num') # The text does not match the pattern.

# DFA coverage inputs are deterministic and traverse every transition.
min_dfa = checker.automata['main'].min_dfa
coverage_inputs = list(dfa_coverage_inputs(min_dfa))
covered_nodes = {min_dfa.start_node}
for text in coverage_inputs:
  node = min_dfa.start_node
  for byte in text:
    node = min_dfa.transitions[node][byte]
    covered_nodes.add(node)
utest_val(set(min_dfa.transitions), covered_nodes, 'nodes reached by the coverage inputs')
utest_seq(coverage_inputs[:3], dfa_coverage_inputs, min_dfa, limit=3)
