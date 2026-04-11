# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from textwrap import dedent

from pithy.datatree import render_datatree
from utest import utest


# Leaf values at the root render via repr with a trailing newline.
utest('0\n', render_datatree, 0)
utest("'hello'\n", render_datatree, 'hello')
utest('None\n', render_datatree, None)

# Empty containers at the root produce no output (zero items to render).
utest('', render_datatree, {})
utest('', render_datatree, [])

# Simple mapping with identifier keys and leaf values.
utest(dedent('''\
    * a: 1
    * b: 2
    '''),
  render_datatree, {'a': 1, 'b': 2})

# Non-identifier keys and non-string keys use repr.
utest(dedent('''\
    * 'my-key': 'x'
    * 1: 'one'
    '''),
  render_datatree, {'my-key': 'x', 1: 'one'})

# Nested mapping value breaks to the next indent level.
utest(dedent('''\
    * a:
      * b: 1
    * c: 2
    '''),
  render_datatree, {'a': {'b': 1}, 'c': 2})

# Nested sequence value inside a mapping.
utest(dedent('''\
    * a:
      0. 2
      1. 3
    '''),
  render_datatree, {'a': [2, 3]})

# Empty container as a value renders inline.
utest(dedent('''\
    * a: []
    * b: {}
    '''),
  render_datatree, {'a': [], 'b': {}})

# Sequences with default numbered prefix are right-justified to the widest index.
utest(dedent('''\
     0. 0
     1. 1
     2. 2
     3. 3
     4. 4
     5. 5
     6. 6
     7. 7
     8. 8
     9. 9
    10. 10
    '''),
  render_datatree, list(range(11)))

# List of dicts: each item's header is on its own line, children indented.
utest(dedent('''\
    0.
      * a: 1
    1.
      * b: 2
    '''),
  render_datatree, [{'a': 1}, {'b': 2}])

# Custom mapping_symbol and sequence_symbol.
utest(dedent('''\
    - a:
      > 1
      > 2
    '''),
  render_datatree, {'a': [1, 2]}, mapping_symbol='-', sequence_symbol='>')

# Initial indent parameter prefixes every line.
utest('  * a: 1\n', render_datatree, {'a': 1}, indent=1)

# Tuples are treated as sequences.
utest(dedent('''\
    0. 10
    1. 20
    '''),
  render_datatree, (10, 20))

# Deeply nested structure.
utest(dedent('''\
    * root:
      * child:
        0. 1
        1. 2
    '''),
  render_datatree, {'root': {'child': [1, 2]}})
