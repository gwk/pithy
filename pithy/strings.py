# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


def string_contains(string, query):
  return string.find(query) != -1


def iter_excluding_str(seq):
  '''
  Often we want to handle all iterables in a particular way, except for str.
  There are two common reasons why:
  * because str should be treated as an atom/leaf value in a nested structure;
  * because the fact that elements of a str are themselves strings,
    which makes naive type-based recursion over sequences impossible.
  ''' 
  if isinstance(seq, str):
    raise TypeError('iter_excluding_str explictly treats str as non-iterable type')
  return iter(seq) # raises TypeError for non-iterables.


def plural_s(count):
  return '' if count == 1 else 's'


def  clip_suffix(string, suffix):
  if len(suffix) == 0: return string # need this case because string[:-0] == ''.
  if not string.endswith(suffix): raise ValueError(string, suffix)
  return string[:-len(suffix)]


_byte_count_dec_magnitudes = [
  ('B',  'byte'),
  ('kB', 'kilobyte'),
  ('MB', 'megabyte'),
  ('GB', 'gigabyte'),
  ('TB', 'terabyte'),
  ('PB', 'petabyte'),
  ('EB', 'exabyte'),
  ('ZB', 'zettabyte'),
  ('YB', 'yottabyte'),
]

def format_byte_count_dec(count, precision=2, abbreviated=True, small_ints=True):
  if small_ints and count < 1000:
    fmt = '{} {}'
  else:
    fmt = '{:.{precision}f} {}'
    count = float(count)
  for abbrev, full in _byte_count_dec_magnitudes:
    if count < 1000: break
    count /= 1000
  return fmt.format(count, abbrev if abbreviated else plural_s(full), precision=precision)


