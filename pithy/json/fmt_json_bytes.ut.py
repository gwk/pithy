# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.json.fmt import fmt_json_bytes
from utest import utest


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


malformed_examples = [
  b'[\n',
  b'{\n',
  b'[ 0\n',
  b'[ 0 ]]\n',
  b'{ "a": 1\n',
  b'[ [ 0\n',
  b'[ { "a": 1\n',

b'''\
{ "a": [
    0 }]
''',

]


trailing_commas = {
  b'[ 0, ]\n' : b'[ 0 ]\n',
  b'{ "a": 1, }\n' : b'{ "a": 1 }\n',

b'''\
[ { "a": 1, },
  { "b": 2, }, ]
''': b'''\
[ { "a": 1 },
  { "b": 2 } ]
''',


b'''\
{ "a": [
    0,
    1, ],
  "b": {
    "x": 0,
    "y": 1, }, ]
''' : b'''\
{ "a": [
    0,
    1 ],
  "b": {
    "x": 0,
    "y": 1 } ]
''',
}


def test_fmt(bytes:bytes, **opts:Any) -> bytes:
  return b''.join(fmt_json_bytes(bytes, **opts))


for clean in clean_examples:
  utest(clean, test_fmt, clean, allow_trailing_commas=True)


for malformed in malformed_examples:
  utest(malformed, test_fmt, malformed, allow_trailing_commas=True)


for malformed, fixed in trailing_commas.items():
  utest(malformed, test_fmt, malformed, allow_trailing_commas=True)
  utest(fixed, test_fmt, malformed, allow_trailing_commas=False)
