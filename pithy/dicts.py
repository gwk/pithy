# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


def set_defaults(d: dict, defaults: dict):
  for k, v in defaults.items():
    d.setdefault(k, v)
  return d


class DefaultByKeyDict(dict):

  def __init__(self, default_factory, *args, **kwargs):
    self.default_factory = default_factory
    super().__init__(*args, **kwargs)

  def __missing__(self, key):
    val = self.default_factory(key)
    self[key] = val
    return val
