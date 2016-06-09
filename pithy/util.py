# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

def plural_s(count):
  return '' if count == 1 else 's'


def set_defaults(d: dict, defaults: dict):
  for k, v in defaults.items():
    d.setdefault(k, v)
  return d


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
