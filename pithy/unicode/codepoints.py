# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Iterable

from . import CodeRange


__all__ = [
  'codes_desc',
]


def codes_desc(code_ranges:Iterable[CodeRange], raw:bool=False) -> str:
  if raw:
    return ' '.join(codes_range_desc(*p) for p in code_ranges) or 'Ø'
  # Calculate single-character subtraction simplifications for ranges.
  ranges:list[CodeRange] = []
  subtracted:set[int] = set()
  for r in code_ranges: # Assumed to be sorted.
    if ranges:
      p = ranges[-1]
      if p[1] + 1 == r[0] and p[1] != 0x60: # Exclude '`' because it makes standard sym range look weird.
        ranges[-1] = (p[0], r[1])
        subtracted.add(p[1])
      else:
        ranges.append(r)
    else:
      ranges.append(r)
  if not ranges: return 'Ø'
  rs = ' '.join(codes_range_desc(*p) for p in ranges)
  if not subtracted: return rs
  ss = ' '.join(code_desc(c) for c in subtracted)
  return f'{rs} - {ss}'


def codes_range_desc(l:int, h:int) -> str:
  if l + 1 == h: return code_desc(l)
  return '{}..{}'.format(code_desc(l), code_desc(h-1))

def code_desc(c:int) -> str:
  assert isinstance(c, int)
  try: return code_descriptions[c]
  except KeyError: return f'\\{c:02x}/'

code_descriptions:dict[int, str] = {
  -1: 'Ø',
  ord('\a'): '\\a',
  ord('\b'): '\\b',
  ord('\t'): '\\t',
  ord('\n'): '\\n',
  ord('\v'): '\\v',
  ord('\f'): '\\f',
  ord('\r'): '\\r',
  ord(' '): '\\s',
}

code_descriptions.update((i, chr(i)) for i in range(ord('!'), 0x7f))
