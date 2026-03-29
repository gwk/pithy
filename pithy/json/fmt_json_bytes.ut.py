# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.json.fmt import fmt_json_bytes
from utest import utest


examples = [
  b'none\n',
  b'"a"\n',
  b'1\n',
  b'[ ]\n',
  b'{ }\n',
  b'[ 0 ]\n',
  b'{ "a": 1 }\n',

b'''\
[ 0,
  1 ]
''',

b'''\
{ "a": 1,
  "b": 2 }
''',

b'''\
[ [ 0 ]]
''',

b'''\
[ { "a": 1 }]
''',

b'''\
{ "a": [
    0 ]}
''',
]


def fmt(bytes:bytes) -> bytes:
  return b''.join(fmt_json_bytes(bytes))


for example in examples:
  utest(example, fmt, example)
