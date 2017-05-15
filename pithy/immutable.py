# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


class Immutable(object):
  'Base class for immutable objects with write-once attribute behavior.'

  def __init__(self, **kw):
    for k, v in kw.items():
      setattr(self, k, v)

  def __setattr__(self, name, val):
    'write-once check before normal setattr.'
    if hasattr(self, name): raise ValueError(self) # Immutable attribute cannot be mutated.
    object.__setattr__(self, name, val)

  def __delattr__(self, name):
    raise ValueError(self)

  def __getitem__(self, key):
    return getattr(self, key)

  def __repr__(self):
    return 'Immutable({})'.format(', '.join('{}={!r}'.format(k, v) for k, v in sorted(self.__dict__.items())))

  def _asdict(self):
    return dict(self.__dict__)
