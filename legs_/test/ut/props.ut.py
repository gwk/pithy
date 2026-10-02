# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Run the property checks of `legs.props` with generated inputs, and test that they detect faulty lexers.
These tests are kept out of the package source tree because they are too slow for the routine unit tests.
'''

from legs.build import build_lexer_class, build_mode_automata
from legs.parse import Grammar, parse_legs
from legs.props import GrammarChecker, PropertyError, PropsStats
from utest import utest_exc, utest_val


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


# All properties hold for the grammar.
stats = checker.check_all(max_examples=15)
utest_val(True, stats.single_token_examples > 0 and stats.sequence_examples > 0 and stats.coverage_inputs > 0, 'stats')


# The checks detect a lexer that disagrees with the automata.

def check_bad_lexer(bad_grammar_text:str) -> PropsStats:
  'Check a lexer built from a different grammar against the automata of the original grammar.'
  bad_grammar:Grammar = parse_legs('bad', bad_grammar_text)
  bad_checker = GrammarChecker(grammar, Lexer=build_lexer_class('BadLexer', bad_grammar))
  return bad_checker.check_all(max_examples=15)

# Hypothesis shrinks the failing input to a minimal one.
utest_exc(PropertyError("mode 'main': input b'AA': token word:0-1: NFA longest match is 2 bytes; kinds: ['word']."),
  check_bad_lexer, grammar_text.replace('$Ascii_Letter+', '$Ascii_Letter'), _utest_label='shorter match')
utest_exc(PropertyError, check_bad_lexer, grammar_text.replace('if\n', 'if: fi\n'), _utest_label='wrong kind')
utest_exc(PropertyError, check_bad_lexer, grammar_text.replace('inner : paren_o :: inner : paren_c\n', ''),
  _utest_label='missing transition')

# The DFA traversal detects a DFA that matches more than the patterns specify.
def check_extra_transition() -> PropsStats:
  'Add a transition to the minimized DFA so that `word` also matches underscores.'
  automata = list(build_mode_automata(grammar))
  min_dfa = automata[0].min_dfa
  word_node = min_dfa.transitions[min_dfa.start_node][ord('a')]
  min_dfa.transitions[word_node][ord('_')] = word_node
  return GrammarChecker(grammar, automata).check_all(max_examples=15)

utest_exc(PropertyError("mode 'main': input b'A_': token word:0-2: NFA longest match is 1 bytes; kinds: ['word']."),
  check_extra_transition)

# The automata can be provided to avoid building them twice.
utest_val(['main', 'inner'], list(GrammarChecker(grammar, list(build_mode_automata(grammar))).automata), 'modes')
