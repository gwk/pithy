# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.sectsyn import parse_entries
from tolkien import Source, SyntaxError
from utest import utest, utest_exc


def entry_strs(text:str|bytes, slc:slice|None=None, **kwargs:Any) -> list[str]:
  source:Source = Source(name='test', text=text)
  return [source[e] for e in parse_entries(source, slc, raises=True, **kwargs)]


utest([], entry_strs, '')
utest([], entry_strs, '\n  \n')
utest(['a'], entry_strs, 'a')
utest(['a', 'b'], entry_strs, 'a\nb\n')
utest(['a', 'b'], entry_strs, 'a  \n\nb')
#^ Trailing whitespace is omitted from each entry.

# Indented lines continue an entry; blank lines do not end it.
utest(['a:\n  x\n\n\ty', 'b'], entry_strs, 'a:\n  x\n\n\ty\n\nb\n')

# Continuation prefixes.
utest(['a:', '| x', 'b'], entry_strs, 'a:\n| x\nb\n')
utest(['a:\n| x', 'b'], entry_strs, 'a:\n| x\nb\n', continuations=['|'])

# Comment prefixes apply at column 0 only; a comment does not end an entry, and remains in its range if a continuation follows.
utest(['a\n// x\n  // y\n  z', 'b // c'], entry_strs, '// w\na\n// x\n  // y\n  z\nb // c\n', comments=['//'])

# An unclosed delimiter does not affect the following entries.
utest(['a: [x', 'b: y'], entry_strs, 'a: [x\nb: y\n')

# Bytes.
utest(['a:\n| x', 'b'], entry_strs, b'// c\na:\n| x\nb\n', continuations=['|'], comments=[b'//'])

# Ranges.
utest(['b\n  c'], entry_strs, 'a\nb\n  c\nd\n', slice(2, 8))
utest_exc(ValueError('range does not begin at the start of a line: slice(1, 4, None)'), entry_strs, 'abc\nd', slice(1, 4))
utest_exc(ValueError('continuation prefix is empty.'), entry_strs, 'a', continuations=[''])

# Orphan continuation lines.
utest_exc(SyntaxError(slice(2, 3), 'Continuation line has no preceding entry.'), entry_strs, '  x\na\n')

def entries_and_errors(text:str, **kwargs:Any) -> list[Any]:
  'Return the text of each entry and (line text, message) for each error.'
  source = Source(name='test', text=text)
  return [(source[el.syntax], el.msg) if isinstance(el, SyntaxError) else source[el] for el in parse_entries(source, **kwargs)]

utest([
    ('x', 'Continuation line has no preceding entry.'),
    ('| y', 'Continuation line has no preceding entry.'),
    'a\n  z'],
  entries_and_errors, '  x\n| y\na\n  z\n', continuations=['|'])
