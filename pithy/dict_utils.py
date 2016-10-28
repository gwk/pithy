# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, MutableSequence, TypeVar, Union


K = Any # TypeVar('K') # mypy 0.46 does not like this? Also, should be Hashable, which does not appear to exist.
V = Any # TypeVar('V') # same.


def dict_put(d: MutableMapping[K, V], k: K, v: V) -> MutableMapping[K, V]:
  '''
  Put a new key and value in the dictionary, or raise err KeyError if the key already exists.
  Returns the dictionary.
  '''
  if k in d:
    raise KeyError(k)
  d[k] = v
  return d


def dict_list_append(d: Dict[K, List[V]], k: K, v: V) -> Dict[K, List[V]]:
  '''
  Append a value to the list stored under the specified key in the dictionary.
  If the key is not present, an empty list is first inserted.
  Returns the dictionary.
  Note: equivalent behavior can also be achieved with a `defaultdict(list)`.
  '''
  d.setdefault(k, []).append(v)
  return d


def dict_list_extend(d: Dict[K, List[V]], k: K, v: V) -> Mapping[K, List[V]]:
  '''
  Extend a value on the list stored under the specified key in the dictionary.
  If the key is not present, an empty list is first inserted.
  Returns the dictionary.
  Note: equivalent behavior can also be achieved with a `defaultdict(list)`.
  '''
  d.setdefault(k, []).extend(v)
  return d


def dict_set_defaults(d: MutableMapping[K, V], defaults: Union[Mapping[K, V], Sequence[V]]) -> MutableMapping[K, V]:
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


def dict_filter_map(d: MutableMapping[K, V], seq: Sequence[K]) -> Iterable[V]:
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
