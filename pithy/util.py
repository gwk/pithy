# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from itertools import islice


def islice_from(seq, start):
  return islice(seq, start, len(seq))


def plural_s(count):
  return '' if count == 1 else 's'


def set_defaults(d: dict, defaults: dict):
  for k, v in defaults.items():
    d.setdefault(k, v)
  return d


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


def memoize(sentinal=Ellipsis):
  '''
  recursive function memoization decorator.
  results will be memoized by a key that is the tuple of all arguments.
  the sentinal is inserted into the dictionary before the call.
  thus, if the function recurses with identical arguments the sentinal will be returned to the inner calls.
  '''
  if callable(sentinal):
    raise ValueError('sentinal is callable, but should be a simple marker value; did you mean `@memoize()`?')

  def _memoize(fn):

    class MemoDictRec(dict):
      def __call__(self, *args):
        return self[args]
      def __missing__(self, args):
        self[args] = sentinal
        res = fn(*args)
        self[args] = res
        return res

    return MemoDictRec()

  return _memoize
