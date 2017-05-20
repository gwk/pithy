# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


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


class lazy_property(object):

  def __init__(self, acc_fn):
    self.acc_fn = acc_fn

  def __get__(self, obj, cls):
    val = self.acc_fn(obj)
    setattr(obj, self.acc_fn.__name__, val)
    return val
