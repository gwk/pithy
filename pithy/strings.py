# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


def string_contains(string, query):
  'Return True if string contains query.'
  return string.find(query) != -1


def strip_prefix(string, prefix, req=True):
  'Remove the prefix if it exists, or raise ValueError.'
  if string.startswith(prefix):
    return string[len(prefix):]
  elif req:
    raise ValueError(string)
  return string


def strip_suffix(string, suffix, req=True):
  'Remove the suffix if it exists, or raise ValueError.'
  if string.endswith(suffix):
    return string[:len(suffix)]
  elif req:
    raise ValueError(string)
  return string


def strip_first_prefix(string, prefixes, req=True):
  'Remove the first prefix from string found in a list of prefixes.'
  for p in prefixes:
    try:
      return strip_prefix(string, p, req=True)
    except ValueError:
      continue
  if req:
    raise ValueError(string)
  return string


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
  "Return an 's' or '' depending on the count, for use in english language formatted strings."
  return '' if count == 1 else 's'


def  clip_suffix(string, suffix):
  'Return the string with the suffix removed if it is present, or raise ValueError.'
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
  "Format a string for the given number of bytes, using the largest appropriate prefix (e.g. 'kB')"
  if small_ints and count < 1000:
    fmt = '{} {}'
  else:
    fmt = '{:.{precision}f} {}'
    count = float(count)
  for abbrev, full in _byte_count_dec_magnitudes:
    if count < 1000: break
    count /= 1000
  return fmt.format(count, abbrev if abbreviated else plural_s(full), precision=precision)


