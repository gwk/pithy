# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from typing import Mapping, Sequence, Union

def dict_put(d: dict, k, v):
  '''
  Put a new key and value in the dictionary, or raise err KeyError if the key already exists.
  Returns the dictionary.
  '''
  if k in d:
    raise KeyError(k)
  d[k] = v
  return d


def dict_list_append(d: dict, k, v):
  '''
  Append a value to the list stored under the specified key in the dictionary.
  If the key is not present, an empty list is first inserted.
  Returns the dictionary.
  '''
  d.setdefault(k, []).append(v)
  return d


def dict_list_extend(d: dict, k, v):
  '''
  Extend a value on the list stored under the specified key in the dictionary.
  If the key is not present, an empty list is first inserted.
  Returns the dictionary.
  '''
  d.setdefault(k, []).extend(v)
  return d


def dict_set_defaults(d: dict, defaults: Union[Mapping, Sequence]):
  '''
  Call setdefault on the dictionary for each item in `defaults`,
  which can be either dictionary-like object implementing `items()` or a sequence of pairs.
  Returns the dictionary.
  '''
  try: it = defaults.items() # type: ignore.
  except AttributeError: it = defaults
  for k, v in it:
    d.setdefault(k, v)
  return d


def dict_filter_map(d: dict, seq):
  'Map the values of `seq` through the dictionary, dropping any elements not in the dictionary.'
  for el in seq:
    try:
      yield d[el]
    except KeyError:
      pass


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
