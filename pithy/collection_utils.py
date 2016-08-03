# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from types import MappingProxyType


def freeze(value, dicts=True, lists=True, sets=True, bytearrays=True):
  if dicts and isinstance(value, dict):
    return MappingProxyType({k: freeze(v) for k, v in value.items()})
  if lists and isinstance(value, list):
    return tuple(freeze(el) for el in value)
  if sets and isinstance(value, set):
    return frozenset(freeze(el) for el in value)
  if bytearrays and isinstance(value, bytearray):
    return bytes(value)
  return value
