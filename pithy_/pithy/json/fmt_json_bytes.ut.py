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
  b'/* comment */[ 1 ]\n' : b'[ 1 ]\n',
  b'[ 1, /* comment */\n  2 ]\n' : b'[ 1,\n  2 ]\n',
  b'[ 1 /* comment */ ]\n' : b'[ 1 ]\n',
  # Multi-line block comment.
  b'[ 1, /* line1\nline2 */\n  2 ]\n' : b'[ 1,\n  2 ]\n',
  # Comments inside strings are NOT stripped.
  b'"a // b"\n' : b'"a // b"\n',
  b'"a /* b */ c"\n' : b'"a /* b */ c"\n',
  # Empty comments.
  b'[ //\n 1 ]\n' : b'[ 1 ]\n',
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

# An unterminated `/* ...` block comment is preserved at EOF rather than swallowing the remaining input.
utest(b'/* never closed\n[1]', test_fmt, b'/* never closed\n[1]', fix=True)
