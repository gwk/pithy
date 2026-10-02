# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from legs.parse import parse_legs
from utest import utest


def parse(text:str) -> tuple[str,list[str],dict[str,list[str]],dict[str,Any]]:
  'Return the license, pattern names, modes and transitions of the grammar.'
  g = parse_legs('test', text)
  return (g.license, list(g.patterns), {name: sorted(kinds) for name, kinds in g.modes.items()}, g.transitions)


def pattern_descs(text:str) -> dict[str,str]:
  'Return the regex of each pattern.'
  return {name: pattern.gen_regex(flavor='py.re') for name, pattern in parse_legs('test', text).patterns.items()}


utest(('', [], {'main': []}, {}), parse, '')

# Text preceding the first header is treated as patterns.
utest(('', ['a', 'b'], {'main': ['a', 'b']}, {}), parse, '// Comment.\na\nb: c\n')

# The license consists of the inline title content and the body; the separator is omitted.
utest(('CC0.', [], {'main': []}, {}), parse, '# License: CC0.\n')
utest(('CC0: https://x.\nMore.', ['a'], {'main': ['a']}, {}), parse, '# License: CC0: https://x.\nMore.\n\n# Patterns\na\n')

# Section names are not case sensitive; headers can have trailing comments.
utest(('', ['a'], {'m': ['a']}, {}), parse, '# patterns // Comment.\na\n# MODES // Comment: with colon.\nm: a\n')

# Sections can appear in any order and can be repeated.
utest(('', ['a', 'b', 'c'], {'m': ['a', 'b'], 'n': ['c']}, {'m': {'a': ('n', 'c')}}), parse, '''
# Transitions
m : a :: n : c

# Modes
m: a b // Comment.

# Patterns
a
b

# Modes
n:
  c

# Patterns
c
''')

# A header ends the preceding entry, regardless of its indented continuation lines.
utest({'a': 'x|y'}, pattern_descs, '# Patterns\na:\n  x\n  | y\n# Modes\nmain: a\n')

# Continuation lines are either indented or begin with `|`. Blank lines and comments do not end an entry.
utest({'a': 'x|y|z', 'b': 'w'}, pattern_descs, 'a:\n  x\n| y\n\n// Comment.\n  // Comment.\n  | z\nb: w\n')

# A header requires a space after the `#` at column 0; otherwise `#` is a pattern character.
utest({'a': 'x\\x23\\x23', 'b': '\\x23y'}, pattern_descs, 'a: x\n  # #\nb: #y\n')
