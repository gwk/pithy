# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import (Any, Callable, Dict, Hashable, Iterable, List, Mapping, MutableMapping, NamedTuple, Set, Tuple, TypeVar,
  Union)


_K = TypeVar('_K', bound=Hashable)
_V = TypeVar('_V')


class ConflictingValues(KeyError): pass


class KeyExistingIncoming(NamedTuple):
  'Triple of (key, existing, incoming) for reporting conflicting values.'
  key:Any
  existing:Any
  incoming:Any


def dict_discard(d:MutableMapping[_K,_V], k:_K) -> None:
  'Discard the element at `k` if it exists.'
  try: del d[k]
  except KeyError: pass


def dict_put(d:MutableMapping[_K,_V], k: _K, v: _V) -> MutableMapping[_K,_V]:
  '''
  Put a new key and value in the dictionary, or raise err KeyError if the key already exists.
  Returns the dictionary.
  '''
  if k in d: raise KeyError(k)
  d[k] = v
  return d


def idemput(d:MutableMapping[_K,_V], k:_K, v:_V) -> MutableMapping[_K,_V]:
  '''
  Put a new key and value in the dictionary;
  raise err KeyError if the key already exists and the existing value is not equal to the incoming one.
  '''
  try: existing = d[k]
  except KeyError: pass
  else:
    if v != existing: raise ConflictingValues(KeyExistingIncoming(k, existing, v))
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


_VH = TypeVar('_VH', bound=Hashable)
_S = Set[_VH]
_I = Iterable[_VH]

def dict_update_sets(d:MutableMapping[_K,_S], update:Union[Mapping[_K, _I],Iterable[Tuple[_K,_I]]]) -> MutableMapping[_K, _S]:
  it:Iterable[Tuple[_K,_I]]
  if isinstance(update, Mapping):
    it = update.items()
  else:
    it = update
  for k, i in it:
    try: s = d[k]
    except KeyError:
      s = set()
      d[k] = s
    s.update(i)
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


class DefaultByKeyDict(Dict[_K,_V]):
  '''
  Subclass of Dict, similar to DefaultDict.
  When a key is missing, default_factory is called with the key as the sole argument.
  '''
  def __init__(self, default_factory:Callable[[_K], _V], *args, **kwargs):
    self.default_factory = default_factory
    super().__init__(*args, **kwargs)

  def __missing__(self, key):
    val = self.default_factory(key)
    self[key] = val
    return val
