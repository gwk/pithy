# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.sectsyn import parse_sections, SectIndices
from tolkien import Source
from utest import utest_seq


source:Source[str]|Source[bytes] = Source(name='empty', text='')
utest_seq([SectIndices(0, 0, -1, slice(0, 0), slice(0, 0))],
  parse_sections, source, symbol='$')

source = Source(name='bare text', text='abc\n')
utest_seq([SectIndices(0, 0, -1, slice(0,0), slice(0,4))],
  parse_sections, source, symbol='$')

source = Source(name='bare text with excess whitespace', text='\nabc\n\n')
utest_seq([SectIndices(0, 0, -1, slice(0,0), slice(1,5))],
  parse_sections, source, symbol='$')

source = Source(name='one section', text='\n$ Title\nBody.\n\n')
utest_seq([
  SectIndices(0, 0, -1, slice(0,0), slice(0,0)),
  SectIndices(1, 1, 0, slice(3,8), slice(9,15)),
], parse_sections, source, symbol='$')


source = Source(name='one section', text=b'\n$ Title\nBody.\n\n')
utest_seq([
  SectIndices(0, 0, -1, slice(0,0), slice(0,0)),
  SectIndices(1, 1, 0, slice(3,8), slice(9,15)),
], parse_sections, source, symbol='$')


def section_tuples(source:Source[str], symbol:str) -> list[tuple[int,str,str]]:
  return [(s.level, source[s.title], source[s.body]) for s in parse_sections(source, symbol=symbol, raises=True)]

text='''
$ 1A
a.

$$ 2B
b.

$ 1C
c.
'''

exp_tuples = [
  (0, '', ''),
  (1, '1A', 'a.\n'),
  (2, '2B', 'b.\n'),
  (1, '1C', 'c.\n'),
]

for symbol in '$§':
  for as_bytes in [False, True]:
    str_text = text.replace('$', symbol)
    if as_bytes:
      source = Source(name=f'sections ({symbol}, bytes)', text=str_text.encode())
    else:
      source = Source(name=f'sections ({symbol}, str)', text=str_text)
    utest_seq(exp_tuples, section_tuples, source, symbol)
