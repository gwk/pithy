# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.seq import seq_int_closed_intervals


__all__ = [
  'codes_desc',
]


def codes_desc(codes):
  return ' '.join(codes_interval_desc(*p) for p in seq_int_closed_intervals(sorted(codes)))

def codes_interval_desc(l, h):
  if l == h: return code_desc(l)
  return '{}-{}'.format(code_desc(l), code_desc(h))

def code_desc(c):
  try: return code_descriptions[c]
  except KeyError: return '{:02x}'.format(c)

code_descriptions = {c : '{:02x}'.format(c) for c in range(0x100)}

code_descriptions.update({
  -1: 'Ø',
  ord('\a'): '\\a',
  ord('\b'): '\\b',
  ord('\t'): '\\t',
  ord('\n'): '\\n',
  ord('\v'): '\\v',
  ord('\f'): '\\f',
  ord('\r'): '\\r',
  ord(' '): '\_',
})

code_descriptions.update((i, chr(i)) for i in range(ord('!'), 0x7f))


