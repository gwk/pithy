# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.hss import HssSection, parse_sections
from tolkien import Source
from utest import utest_seq


source = Source(name='empty', text='')
utest_seq([HssSection(0, 0, -1, slice(0, 0), slice(0, 0))],
  parse_sections, source)

source = Source(name='bare text', text='abc\n')
utest_seq([HssSection(0, 0, -1, slice(0,0), slice(0,4))],
  parse_sections, source)

source = Source(name='bare text with excess whitespace', text='\nabc\n\n')
utest_seq([HssSection(0, 0, -1, slice(0,0), slice(1,5))],
  parse_sections, source)

source = Source(name='one section', text='\n# Title\nBody.\n\n')
utest_seq([
  HssSection(0, 0, -1, slice(0,0), slice(0,0)),
  HssSection(1, 1, 0, slice(3,8), slice(9,15)),
], parse_sections, source)



def section_tuples(source:Source[str]) -> list[tuple[int,str,str]]:
  return [(s.level, source[s.title], source[s.body]) for s in parse_sections(source)]

source = Source(name='sections', text='''
# 1A
a.

## 2B
b.

# 1C
c.
''')

utest_seq([
  (0, '', ''),
  (1, '1A', 'a.\n'),
  (2, '2B', 'b.\n'),
  (1, '1C', 'c.\n'),
], section_tuples, source)
