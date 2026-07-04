# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.json.fmt import fmt_json_bytes
from utest import utest


def test_fmt(bytes:bytes, **opts:Any) -> bytes:
  return b''.join(fmt_json_bytes(bytes, **opts))


clean_examples = [
  b'',
  b'null\n',
  b'"a"\n',
  b'1\n',
  b'[]\n',
  b'{}\n',
  b'[ 0 ]\n',
  b'{ "a": 1 }\n',
  b'[ {}]\n',
  b'[ [ 0 ]]\n',
  b'[ { "a": 1 }]\n',

b'''\
[ 0,
  1 ]
''',

b'''\
{ "a": 1,
  "b": 2 }
''',

b'''\
[ [],
  []]
''',

b'''\
[ [ 0 ],
  [ 1 ]]
''',

b'''\
[ [ 0,
    1 ],
  [ 2,
    3 ]]
''',

b'''\
[ { "a": 1,
    "b": 2 },
  { "c": 3,
    "d": 4 }]
''',

b'''\
{ "a": [
    0 ],
  "b": {
    "x": 0 }}
''',
]

for clean in clean_examples:
  utest(clean, test_fmt, clean, fix=False)


malformed_examples = [
  b'[\n',
  b'{\n',
  b'[ 0\n',
  b'[ 0 ]]\n',
  b'{ "a": 1\n',
  b'[ [ 0\n',
  b'[ { "a": 1\n',
  b'[ ,\n',
  b',]\n',
  b'"a""b"\n',

b'''\
{ "a": [
    0 }]
''',

b'''\
[ 0
  0 ]
''',
]

for malformed in malformed_examples:
  utest(malformed, test_fmt, malformed, fix=False)


fix_examples = {
b'''\
[]
0
''' : b'''\
[],
0
''',

b'''\
[ "a"
  "b" ]
''' : b'''\
[ "a",
  "b" ]
''',

b'''\
[ []
  []]
''' : b'''\
[ [],
  []]
''',

b'''\
[ { "a": 1 }
  { "b": 2 }]
''' : b'''\
[ { "a": 1 },
  { "b": 2 }]
''',

b'''\
[ 0,,
  1 ]
''' : b'''\
[ 0,
  1 ]
''',
}

for malformed, fixed in fix_examples.items():
  utest(malformed, test_fmt, malformed, fix=False)
  utest(fixed, test_fmt, malformed, fix=True)


trailing_commas_examples = {
  b'[ 0,]\n' : b'[ 0 ]\n',
  b'{ "a": 1,}\n' : b'{ "a": 1 }\n',

b'''\
[ { "a": 1,},
  { "b": 2,},]
''': b'''\
[ { "a": 1 },
  { "b": 2 }]
''',

b'''\
{ "a": [
    0,
    1,],
  "b": {
    "x": 0,
    "y": 1,},]
''' : b'''\
{ "a": [
    0,
    1 ],
  "b": {
    "x": 0,
    "y": 1 }]
''',
}


for with_trailing, without_trailing in trailing_commas_examples.items():
  utest(with_trailing, test_fmt, with_trailing, fix=True, allow_trailing_commas=True)
  utest(without_trailing, test_fmt, with_trailing, fix=True, allow_trailing_commas=False)


# Comments.

comment_examples = {
  # Line comments.
  b'[ 1 ] // comment\n' : b'[ 1 ]\n',
  b'// comment\n[ 1 ]\n' : b'[ 1 ]\n',
  b'[ 1, // comment\n  2 ]\n' : b'[ 1,\n  2 ]\n',
  b'[ 1 // comment\n ]\n' : b'[ 1 ]\n',
  # Block comments.
  b'[ 1 ] /* comment */\n' : b'[ 1 ]\n',
  b'/* comment */ [ 1 ]\n' : b'[ 1 ]\n',
  b'[ 1, /* comment */\n  2 ]\n' : b'[ 1,\n  2 ]\n',
  b'[ 1 /* comment */ ]\n' : b'[ 1 ]\n',
  # Multi-line block comment.
  b'[ 1, /* line1\nline2 */\n  2 ]\n' : b'[ 1,\n  2 ]\n',
  # Comments inside strings are NOT stripped.
  b'"a // b"\n' : b'"a // b"\n',
  b'"a /* b */ c"\n' : b'"a /* b */ c"\n',
  # Empty comments.
  b'[ //\n  1 ]\n' : b'[ 1 ]\n',
  b'[ /**/ 1 ]\n' : b'[ 1 ]\n',
}

for with_comments, stripped in comment_examples.items():
  utest(with_comments, test_fmt, with_comments, fix=True, allow_comments=True)
  utest(stripped, test_fmt, with_comments, fix=True, allow_comments=False)


# Comment whitespace.

comment_whitespace_examples = {
  b'[1]// c\n' : b'[ 1 ] // c\n',
  b'[1// c\n,2]' : b'[ 1 // c\n,\n  2 ]\n',
  b'[1,/* c */2]' : b'[ 1, /* c */\n  2 ]\n',
  b'{"a":1// c\n,"b":2}' : b'{ "a": 1 // c\n,\n  "b": 2 }\n',
}

for with_comments, expected in comment_whitespace_examples.items():
  utest(expected, test_fmt, with_comments, fix=False)
  utest(expected, test_fmt, with_comments, fix=True, allow_comments=True)

# A bare `/` not followed by `/` or `*` is preserved as a literal token rather than silently dropped.
utest(b'[ 1/2 ]\n', test_fmt, b'[1/2]', fix=True)

# A bare `/` at EOF is preserved rather than dropped.
utest(b'/\n', test_fmt, b'/', fix=False)
utest(b'5/\n', test_fmt, b'5/', fix=False)
utest(b'5\n/\n', test_fmt, b'5 /', fix=False) # Whitespace-separated tokens break, same as the mid-stream orphan slash.
utest(b'[ 1/\n', test_fmt, b'[1/', fix=True)

# An unterminated `/* ...` block comment is preserved at EOF rather than swallowing the remaining input.
utest(b'/* never closed\n[1]\n', test_fmt, b'/* never closed\n[1]', fix=True)


# Comment placement: well-placed preserved comments are fixed points of the formatter.

comment_placement_examples = [
  b'[ 1,\n  // c\n  2 ]\n', # An own-line comment keeps its own line and indent.
  b'[ 1,\n  // a\n  // b\n  2 ]\n', # Consecutive own-line comments are each indented.
  b'[ 1,\n  // a\n\n  // b\n  2 ]\n', # A single blank line between comments is preserved.
  b'{ // intro\n  "a": 1 }\n', # The first child after an attached comment is indented.
  b'{\n  // c\n  "a": 1 }\n', # An own-line comment directly after an open bracket.
  b'{ "a": // c\n  1 }\n', # A value after a comment attached to its colon is indented.
  b'[ 1\n  // c\n ]\n', # An own-line comment before a close bracket.
  b'[ 1 /* a */ /* b */ ]\n', # Adjacent block comments keep a separating space.
  b'/* a */ /* b */ 1\n', # Leading block comments are separated from each other and the first token.
  b'/* a */\n// b\n5\n', # A line comment on its own line after a block comment.
]

for placed in comment_placement_examples:
  utest(placed, test_fmt, placed, fix=False)
  utest(placed, test_fmt, placed, fix=True, allow_comments=True)


# Nonstandard comment placement is normalized.

comment_placement_norm_examples = {
  b'[ 1,\n// c\n2 ]\n' : b'[ 1,\n  // c\n  2 ]\n', # Own-line comments are indented.
  b'/* a *//* b */\n' : b'/* a */ /* b */\n', # Adjacent block comments are separated by a space.
  b'/* a */1\n' : b'/* a */ 1\n', # The first token is separated from a leading block comment.
}

for unplaced, placed in comment_placement_norm_examples.items():
  utest(placed, test_fmt, unplaced, fix=False)
  utest(placed, test_fmt, unplaced, fix=True, allow_comments=True)


# Comment-only input gets a final newline like any other non-empty output.

utest(b'// c\n', test_fmt, b'// c', fix=False)
utest(b'/* c */\n', test_fmt, b'/* c */', fix=False)
utest(b'', test_fmt, b'// c', fix=True)
utest(b'', test_fmt, b'/* c */', fix=True)


# Fix mode interacting with comments.

# A comma inserted after an own-line comment goes on its own line; this shape is stable under reformatting.
utest(b'[ 1\n  // c\n,\n  2 ]\n', test_fmt, b'[ 1\n  // c\n  2 ]\n', fix=True, allow_comments=True)
# A trailing comma is removed across a stripped comment.
utest(b'[ 1 ]\n', test_fmt, b'[ 1, /* c */ ]\n', fix=True)
# Known limitation: a trailing comma is not removed when a preserved comment attaches to it first,
# because the comma has already been emitted by the time the close bracket is seen.
utest(b'[ 1, // c\n ]\n', test_fmt, b'[ 1, // c\n ]\n', fix=True, allow_comments=True)


# Chunk-boundary behavior: output must not depend on the chunk size of the input reader.

class CappedReader:
  'A binary reader that returns at most `cap` bytes per read, to exercise resumption of every machine state.'

  def __init__(self, data:bytes, cap:int) -> None:
    self.data = data
    self.cap = cap
    self.pos = 0

  def read(self, size:int=-1, /) -> bytes:
    n = min(self.cap, size) if size >= 0 else self.cap
    b = self.data[self.pos:self.pos+n]
    self.pos += len(b)
    return b


def test_fmt_capped(data:bytes, cap:int, **opts:Any) -> bytes:
  return b''.join(fmt_json_bytes(CappedReader(data, cap), **opts))


chunk_cases:list[tuple[bytes,dict[str,Any]]] = [
  *((ex, {'fix':False}) for ex in clean_examples),
  *((ex, {'fix':False}) for ex in malformed_examples),
  *((ex, {'fix':True}) for ex in fix_examples),
  *((ex, {'fix':True, 'allow_trailing_commas':True}) for ex in trailing_commas_examples),
  *((ex, {'fix':True, 'allow_trailing_commas':False}) for ex in trailing_commas_examples),
  *((ex, {'fix':True}) for ex in comment_examples),
  *((ex, {'fix':True, 'allow_comments':True}) for ex in comment_examples),
  *((ex, {'fix':False}) for ex in comment_whitespace_examples),
  *((ex, {'fix':False}) for ex in comment_placement_examples),
  *((ex, {'fix':False}) for ex in comment_placement_norm_examples),
  (b'[1/2]', {'fix':True}),
  (b'/', {'fix':False}),
  (b'5/', {'fix':False}),
  (b'5 /', {'fix':False}),
  (b'[1/', {'fix':True}),
  (b'// c', {'fix':False}),
  (b'/* c */', {'fix':False}),
  (b'/* never closed\n[1]', {'fix':True}),
  (b'[ 1\n  // c\n  2 ]\n', {'fix':True, 'allow_comments':True}),
]

for data, opts in chunk_cases:
  whole = test_fmt(data, **opts)
  for cap in (1, 2, 3, 7):
    utest(whole, test_fmt_capped, data, cap, **opts)
