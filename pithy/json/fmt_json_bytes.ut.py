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
