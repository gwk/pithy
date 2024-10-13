# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, Hashable, Iterable, Mapping, MutableMapping, TypeVar

from .exceptions import ConflictingValues


_K = TypeVar('_K', bound=Hashable)
_V = TypeVar('_V')
_VH = TypeVar('_VH', bound=Hashable)


def dict_strict_inverse(d:Mapping[_K,_V]) -> dict[_V,_K]:
  '''
  Given a mapping from keys to values, return a mapping from values to keys.
  Raises `ConflictingValues` if the values are not unique.
  '''
  inverse:dict[_V,_K] = {}
  for k, v in d.items():
    if v in inverse: raise ConflictingValues(key=v, existing=inverse[v], incoming=k)
    inverse[v] = k
  return inverse


def dict_dag_inverse(d:Mapping[_K,Iterable[_VH]]) -> dict[_VH,set[_K]]:
  '''
  Given a mapping from keys to iterables of hashable values, return a mapping from values to sets of keys.
  '''
  inverse:dict[_VH,set[_K]] = {}
  for k, vs in d.items():
    for v in vs:
      dict_update_set(inverse, v, k)
  return inverse


def dict_dag_inverse_with_all_keys(d:Mapping[_K,Iterable[_K]]) -> dict[_K,set[_K]]:
  '''
  Given a mapping from keys to iterables of keys, return an inverse mapping from keys to sets of keys,
  including all of the original keys that mapped to empty iterables.
  '''
  inverse:dict[_K,set[_K]] = { k: set() for k in d }
  for k, ks in d.items():
    for v in ks:
      dict_update_set(inverse, v, k)
  return inverse


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
  raise `ConflictingValues` if the key already exists and the existing value is not equal to the incoming one.
  '''
  try: existing = d[k]
  except KeyError: pass
  else:
    if v != existing: raise ConflictingValues(key=k, existing=existing, incoming=v)
  d[k] = v
  return d


def dict_list_append(d: dict[_K, list[_V]], k: _K, v: _V) -> dict[_K, list[_V]]:
  '''
  Append a value to the list stored under the specified key in the dictionary.
  If the key is not present, an empty list is first inserted.
  Returns the dictionary.
  Note: equivalent behavior can also be achieved with a `defaultdict(list)`.
  '''
  d.setdefault(k, []).append(v)
  return d


def dict_list_append_items(d:dict[_K, list[_V]], items:Iterable[tuple[_K,_V]]) -> dict[_K, list[_V]]:
  '''
  Append each value in the iterable to the list stored under the specified key in the dictionary.
  If the key is not present, an empty list is first inserted.
  Returns the dictionary.
  '''
  for k, v in items:
    d.setdefault(k, []).append(v)
  return d


def dict_list_extend(d: dict[_K, list[_V]], k: _K, v: Iterable[_V]) -> dict[_K, list[_V]]:
  '''
  Extend a value on the list stored under the specified key in the dictionary.
  If the key is not present, an empty list is first inserted.
  Returns the dictionary.
  Note: equivalent behavior can also be achieved with a `defaultdict(list)`.
  '''
  d.setdefault(k, []).extend(v)
  return d


def dict_set_defaults(d: MutableMapping[_K, _V], defaults: Mapping[_K, _V]|Iterable[tuple[_K, _V]]) -> MutableMapping[_K, _V]:
  '''
  Call setdefault on the dictionary `d` for each item in `defaults` and return `d`.
  `defaults` can be either dictionary-like object implementing `items()` or a sequence of pairs.
  '''
  it: Iterable[tuple[_K, _V]]
  if isinstance(defaults, Mapping):
    it = defaults.items()
  else:
    it = defaults
  for k, v in it:
    d.setdefault(k, v)
  return d


_S = set[_VH]
_I = Iterable[_VH]

def dict_update_set(d:MutableMapping[_K,_S], k:_K, el:_VH) -> None:
  '''
  Given a mutable mapping `d` of keys:_K to sets of hashable elements:_VH,
  add `el` to the set at `k`.
  '''
  try: s = d[k]
  except KeyError:
    s = set()
    d[k] = s
  s.add(el)


def dict_update_sets(d:MutableMapping[_K,_S], update:Mapping[_K, _I]|Iterable[tuple[_K,_I]]) -> MutableMapping[_K, _S]:
  '''
  Given a mutable mapping `d` and a mapping or iterable of pairs `update`,
  update the sets in `d` with the values in the incoming sets.
  For each key in `update`, if the key is not present in `d`, a new set is created.
  '''
  it:Iterable[tuple[_K,_I]]
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


def dict_fan_by_key_pred(d: Mapping[_K, _V], pred: Callable[[_K], bool]) -> tuple[dict[_K, _V], dict[_K, _V]]:
  'Fan out `d` into a pair of dictionaries by applying `pred` to each key in `d`.'
  fan: tuple[dict[_K, _V], dict[_K, _V]] = ({}, {})
  for k, v in d.items():
    if pred(k):
      fan[1][k] = v
    else:
      fan[0][k] = v
  return fan


def dict_remap_keys(d:Mapping[_K,_V], remap:dict[_K,_K]) -> dict[_K,_V]:
  '''
  Remap the keys of `d` using the mapping `remap`.
  Keys not  in `remap` are left unchanged.
  Always returns a new dictionary, even if no remapping occurs.
  '''
  return { remap.get(k, k) : v for k, v in d.items() }


def dict_remap_keys_mut(d:dict[_K,_V], remap:Mapping[_K,_K]|Iterable[tuple[_K,_K]]) -> dict[_K,_V]:
  '''
  Remap the keys of `d` using the mapping `remap`, modifying `d` in place.
  `remap` can be a dictionary or an iterable of pairs.
  Keys not  in `remap` are left unchanged.
  '''
  if isinstance(remap, Mapping):
    it:Iterable[tuple[_K,_K]] = remap.items()
  else:
    it = remap

  for ko, kr in it:
    try: v = d[ko]
    except KeyError: pass
    else:
      if kr in d: raise RemapKeyError(f'remap key is already present: {kr!r}; original key: {ko!r}')
      d[kr] = v
      del d[ko]

  return d


class RemapKeyError(Exception): pass


class DefaultByKeyDict(dict[_K,_V]):
  '''
  Subclass of dict, similar to defaultdict.
  When a key is missing, default_factory is called with the key as the sole argument.
  '''
  def __init__(self, default_factory:Callable[[_K], _V], *args, **kwargs):
    self.default_factory = default_factory
    super().__init__(*args, **kwargs)

  def __missing__(self, key):
    val = self.default_factory(key)
    self[key] = val
    return val
