# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, Dict, Hashable, Iterable, List, Mapping, MutableMapping, MutableSequence, Sequence, Tuple, TypeVar, Union


_K = TypeVar('_K', bound=Hashable)
_V = TypeVar('_V')


def dict_put(d: MutableMapping[_K, _V], k: _K, v: _V) -> MutableMapping[_K, _V]:
  '''
  Put a new key and value in the dictionary, or raise err KeyError if the key already exists.
  Returns the dictionary.
  '''
  if k in d:
    raise KeyError(k)
  d[k] = v
  return d


def dict_list_append(d: Dict[_K, List[_V]], k: _K, v: _V) -> Dict[_K, List[_V]]:
  '''
  Append a value to the list stored under the specified key in the dictionary.
  If the key is not present, an empty list is first inserted.
  Returns the dictionary.
  Note: equivalent behavior can also be achieved with a `defaultdict(list)`.
  '''
  d.setdefault(k, []).append(v)
  return d


def dict_list_extend(d: Dict[_K, List[_V]], k: _K, v: Iterable[_V]) -> Dict[_K, List[_V]]:
  '''
  Extend a value on the list stored under the specified key in the dictionary.
  If the key is not present, an empty list is first inserted.
  Returns the dictionary.
  Note: equivalent behavior can also be achieved with a `defaultdict(list)`.
  '''
  d.setdefault(k, []).extend(v)
  return d


def dict_set_defaults(d: MutableMapping[_K, _V], defaults: Union[Mapping[_K, _V], Iterable[Tuple[_K, _V]]]) -> MutableMapping[_K, _V]:
  '''
  Call setdefault on the dictionary for each item in `defaults`,
  which can be either dictionary-like object implementing `items()` or a sequence of pairs.
  Returns the dictionary.
  '''
  it: Iterable[Tuple[_K, _V]]
  if isinstance(defaults, Mapping):
    it = defaults.items()
  else:
    it = defaults
  for k, v in it:
    d.setdefault(k, v)
  return d


def dict_fan_by_key_pred(d: Mapping[_K, _V], pred: Callable[[_K], bool]) -> Tuple[Dict[_K, _V], Dict[_K, _V]]:
  'Fan out `d` into a pair of dictionaries by applying `pred` to each key in `d`.'
  fan: Tuple[Dict[_K, _V], Dict[_K, _V]] = ({}, {})
  for k, v in d.items():
    if pred(k):
      fan[1][k] = v
    else:
      fan[0][k] = v
  return fan


class DefaultByKeyDict(dict): # TODO: typing.
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
