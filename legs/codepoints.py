# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import *
from .unico import CodeRange


__all__ = [
  'codes_desc',
]


def codes_desc(code_ranges: Iterable[CodeRange]) -> str:
  return ' '.join(codes_range_desc(*p) for p in code_ranges)

def codes_range_desc(l: int, h: int) -> str:
  if l + 1 == h: return code_desc(l)
  return '{}-{}'.format(code_desc(l), code_desc(h))

def code_desc(c: int) -> str:
  assert isinstance(c, int)
  try: return code_descriptions[c]
  except KeyError: return '{:02x}'.format(c)

code_descriptions: Dict[int, str] = {c : '{:02x}'.format(c) for c in range(0x100)}
# TODO: why fill these out if we fall back on same format?

code_descriptions.update({
  -1: 'Ø',
  ord('\a'): '\\a',
  ord('\b'): '\\b',
  ord('\t'): '\\t',
  ord('\n'): '\\n',
  ord('\v'): '\\v',
  ord('\f'): '\\f',
  ord('\r'): '\\r',
  ord(' '): '\\s',
})

code_descriptions.update((i, chr(i)) for i in range(ord('!'), 0x7f))
