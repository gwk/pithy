# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.sectsyn import parse_sections, SectIndices
from tolkien import Source, SyntaxError
from utest import utest, utest_exc, utest_seq, utest_seq_exc


e0 = slice(0, 0) # The empty slice used for all of the root header ranges.

source:Source[str]|Source[bytes]|Source[bytearray] = Source(name='empty', text='')
utest_seq([SectIndices(0, 0, -1, e0, e0, e0, e0, body=e0, raw_body=e0)],
  parse_sections, source, symbol='$', numbered=False)

source = Source(name='bare text', text='abc\n')
utest_seq([SectIndices(0, 0, -1, e0, e0, e0, e0, body=slice(0,4), raw_body=slice(0,4))],
  parse_sections, source, symbol='$', numbered=False)

source = Source(name='bare text with excess whitespace', text='\nabc\n\n')
utest_seq([SectIndices(0, 0, -1, e0, e0, e0, e0, body=slice(1,5), raw_body=slice(0,6))],
  parse_sections, source, symbol='$', numbered=False)

one_section_exp = [
  SectIndices(0, 0, -1, e0, e0, e0, e0, body=e0, raw_body=slice(0,1)),
  SectIndices(1, 1, 0, marker=slice(1,2), title=slice(3,8), name=slice(3,8), inline=slice(8,8), body=slice(9,15),
    raw_body=slice(9,16)),
]

source = Source(name='one section', text='\n$ Title\nBody.\n\n')
utest_seq(one_section_exp, parse_sections, source, symbol='$', numbered=False)

source = Source(name='one section bytes', text=b'\n$ Title\nBody.\n\n')
utest_seq(one_section_exp, parse_sections, source, symbol='$', numbered=False)

source = Source(name='one section bytearray', text=bytearray(b'\n$ Title\nBody.\n\n'))
utest_seq(one_section_exp, parse_sections, source, symbol='$', numbered=False)
utest_seq(one_section_exp, parse_sections, source, symbol=b'$', numbered=False)


def section_tuples(text:str|bytes, symbol:str='#', numbered:bool=False) -> list[tuple[int,str,str]]:
  source:Source = Source(name='test', text=text)
  return [(s.level, source[s.title], source[s.body])
    for s in parse_sections(source, symbol=symbol, raises=True, numbered=numbered)]


str_text='''
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
  for numbered in [False, True]:
    for as_bytes in [False, True]:
      text = str_text
      if numbered:
        text = text.replace('$$ ', '$2 ').replace('$ ', '$1 ')
      text = text.replace('$', symbol)
      numbered_desc = 'numbered' if numbered else 'repeated'
      utest_seq(exp_tuples, section_tuples, text.encode() if as_bytes else text, symbol=symbol, numbered=numbered,
        _utest_label=f'{symbol}, {numbered_desc}, {"bytes" if as_bytes else "str"}')


# Header on the first line: the root section is empty.

source = Source(name='first line header', text='# A\nbody\n')
utest_seq([
  SectIndices(0, 0, -1, e0, e0, e0, e0, body=e0, raw_body=e0),
  SectIndices(1, 1, 0, marker=slice(0,1), title=slice(2,3), name=slice(2,3), inline=slice(3,3), body=slice(4,9),
    raw_body=slice(4,9)),
], parse_sections, source, symbol='#', numbered=False)


# Header shapes.

utest_seq([(0, '', ''), (1, '', ''), (2, '', '')], section_tuples, '#\n##', _utest_label='all-symbol lines, no final newline')
utest_seq([(0, '', ''), (1, 'A', '')], section_tuples, '# A', _utest_label='title without final newline')
utest_seq([(0, '', ''), (1, 'A', 'b\n')], section_tuples, '#\tA \t\nb\n', _utest_label='tab after marker')

non_header_text = '#foo: x\n#!shebang\n #indented\n # Indented\n'
utest_seq([(0, '', non_header_text)], section_tuples, non_header_text,
  _utest_label='lines that are not headers')

utest_seq([(0, '', '=== odd\n= single\n'), (1, 'A', ''), (2, 'B', '')], section_tuples, '=== odd\n= single\n== A\n==== B\n',
  symbol='==', _utest_label='multi-character symbol')

utest_seq([(0, '', '$100bill\n$ none\n$x\n$\n$²\n'), (1, 'A', '')], section_tuples, '$100bill\n$ none\n$x\n$\n$²\n$1 A\n',
  symbol='$', numbered=True, _utest_label='numbered lines that are not headers')

utest_seq([(0, '', ''), (1, '', ''), (2, '', '')], section_tuples, '$1\n$02', symbol='$', numbered=True,
  _utest_label='numbered all-marker lines')


# Symbol validation.

source = Source(name='validation', text='')
utest_seq_exc(ValueError, parse_sections, source, symbol='', numbered=False)
utest_seq_exc(ValueError, parse_sections, source, symbol='# ', numbered=False)
utest_seq_exc(ValueError, parse_sections, source, symbol=b'#', numbered=False)
utest_seq_exc(ValueError, parse_sections, source, symbol='#', title_sep='', numbered=False)


# Level errors.

def sections_and_errors(text:str, symbol:str='#', numbered:bool=False) -> list[Any]:
  'Return (level, parent_idx, title) for each section and (marker text, message) for each error.'
  source = Source(name='test', text=text)
  return [(source[el.syntax], el.msg) if isinstance(el, SyntaxError) else (el.level, el.parent_idx, source[el.title])
    for el in parse_sections(source, symbol=symbol, numbered=numbered, raises=False)]


skip_text = '# A\n### B\n### C\n## D\n### E\n# F\n'

utest([
  (0, -1, ''),
  (1, 0, 'A'),
  ('###', 'Header level 3 is more than one deeper than parent level 1.'),
  (3, 1, 'B'),
  ('###', 'Header level 3 is more than one deeper than parent level 1.'),
  (3, 1, 'C'),
  (2, 1, 'D'),
  (3, 4, 'E'),
  (1, 0, 'F'),
], sections_and_errors, skip_text)

utest_exc(SyntaxError(slice(4,7), 'Header level 3 is more than one deeper than parent level 1.'), section_tuples, skip_text)

utest([
  (0, -1, ''),
  ('##', 'Header level 2 is more than one deeper than parent level 0.'),
  (2, 0, 'A'),
], sections_and_errors, '## A\n', _utest_label='skip from root')

utest([
  (0, -1, ''),
  ('$100', 'Header level 100 is more than one deeper than parent level 0.'),
  (100, 0, 'bill'),
], sections_and_errors, '$100 bill\n', symbol='$', numbered=True)

utest([
  (0, -1, ''),
  ('$0', 'Header level 0 is reserved for the root section.'),
  (1, 0, 'A'),
], sections_and_errors, '$1 A\n$0 zero\n', symbol='$', numbered=True)

def lenient_bodies(text:str) -> list[tuple[int,str,str]]:
  source = Source(name='test', text=text)
  return [(el.level, source[el.title], source[el.body])
    for el in parse_sections(source, symbol='$', numbered=True, raises=False) if isinstance(el, SectIndices)]

utest([(0, '', ''), (1, 'A', '$0 zero\n')], lenient_bodies, '$1 A\n$0 zero\n', _utest_label='level 0 line remains body text')

utest_exc(SyntaxError(slice(0,2), 'Header level 0 is reserved for the root section.'), section_tuples, '$0 zero\n', symbol='$',
  numbered=True)


# Title splitting.

def title_parts(text:str, title_sep:str|None=':') -> list[tuple[str,str,str]]:
  source = Source(name='test', text=text)
  return [(source[s.title], source[s.name], source[s.inline])
    for s in parse_sections(source, symbol='#', numbered=False, title_sep=title_sep, raises=True)]

title_text = '# License: CC0\n# Patterns\n# a : b: c \n# Empty:\n#\n'

utest([
  ('', '', ''),
  ('License: CC0', 'License', 'CC0'),
  ('Patterns', 'Patterns', ''),
  ('a : b: c', 'a', 'b: c'),
  ('Empty:', 'Empty', ''),
  ('', '', ''),
], title_parts, title_text)

utest([
  ('', '', ''),
  ('License: CC0', 'License: CC0', ''),
  ('Patterns', 'Patterns', ''),
  ('a : b: c', 'a : b: c', ''),
  ('Empty:', 'Empty:', ''),
  ('', '', ''),
], title_parts, title_text, title_sep=None)

utest([('', '', ''), ('a :: b', 'a', 'b')], title_parts, '# a :: b\n', title_sep='::')

source = Source(name='title split bytes', text=b'# License: CC0\n')
utest_seq([
  SectIndices(0, 0, -1, e0, e0, e0, e0, body=e0, raw_body=e0),
  SectIndices(1, 1, 0, marker=slice(0,1), title=slice(2,14), name=slice(2,9), inline=slice(11,14), body=slice(15,15),
    raw_body=slice(15,15)),
], parse_sections, source, symbol='#', numbered=False, title_sep=':')


# Markers and section ranges.

def marker_parts(text:str, symbol:str, numbered:bool) -> list[tuple[str,str]]:
  'Return the marker text and the complete section text.'
  source = Source(name='test', text=text)
  return [(source[s.marker], source[s]) for s in parse_sections(source, symbol=symbol, numbered=numbered, raises=True)]

utest([('', 'pre\n'), ('#', '# A\na\n'), ('##', '## B\n\nb\n\n'), ('#', '#')], marker_parts, 'pre\n# A\na\n## B\n\nb\n\n#',
  symbol='#', numbered=False)

utest([('', ''), ('$1', '$1 A\na\n'), ('$2', '$2 B\n')], marker_parts, '$1 A\na\n$2 B\n', symbol='$', numbered=True)


# Body trimming.

def bodies(text:str) -> list[tuple[str,str]]:
  source = Source(name='test', text=text)
  return [(source[s.body], source[s.raw_body]) for s in parse_sections(source, symbol='#', numbered=False, raises=True)]

utest([
  ('  indented\nx\n', ' \n\n  indented\nx\n\n \n'),
  ('a', '\na  \n\n'),
  ('', ' \n\n'),
  ('', ''),
  ('z', 'z'),
], bodies, ' \n\n  indented\nx\n\n \n# A\n\na  \n\n# B\n \n\n# C\n# D\nz')
