# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


def dict_put(d: dict, k, v):
  'Put a new key and value in the dictionary, raises err KeyError if the key already exists.'
  if k in d:
    raise KeyError(k)
  d[k] = v


def dict_append(d: dict, k, v):
  '''
  Append a value to the list stored under the specified key in the dictionary.
  If the list does not exist, an empty one will be inserted.
  '''
  d.setdefault(k, []).append(v)


def dict_extend(d: dict, k, v):
  '''
  Extend a value on the list stored under the specified key in the dictionary.
  If the list does not exist, an empty one will be inserted.
  '''
  d.setdefault(k, []).extend(v)


def dict_set_defaults(d: dict, defaults: dict):
  'Create a new dictionary with the keys and their values as defaults from the existing dictionary "defaults".'
  for k, v in defaults.items():
    d.setdefault(k, v)
  return d


class DefaultByKeyDict(dict):
  '''
  Subclass of Dict, similar to defaultdict.
  When a key is missing, default_factory is called with the key as the sole argument.
  '''
  def __init__(self, default_factory, *args, **kwargs):
    self.default_factory = default_factory
    super().__init__(*args, **kwargs)

  def __missing__(self, key):
    val = self.default_factory(key)
    self[key] = val
    return val
