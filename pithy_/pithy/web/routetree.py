# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from datetime import date
from re import Pattern
from typing import Any, Callable, cast, Generic, get_args, Literal, Self, TypeVar


ConverterKind = Literal['nat', 'int', 'hex', 'date', 'str', 'path']
converter_kinds = frozenset(get_args(ConverterKind))

_str_chars_pattern_ctor:tuple[frozenset[str],Pattern,Callable[[str],Any]] = (frozenset(), re.compile(r'.+'), str)
#^ Empty chars implies all characters are allowed.

converter_kind_attrs:dict[ConverterKind,tuple[frozenset[str],Pattern,Callable[[str],Any]]] = {
  'nat':  (frozenset('0123456789'), re.compile(r'[0-9]+'), int),
  'int':  (frozenset('+-0123456789'), re.compile(r'[+-]?[0-9]+'), int),
  'hex':  (frozenset('0123456789abcdefABCDEF'), re.compile(r'[0-9a-fA-F]+'), str),
  'date': (frozenset('-0123456789'), re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}'), date.fromisoformat),
  'str':  _str_chars_pattern_ctor,
  'path': _str_chars_pattern_ctor,
}


class RouteComponentPattern:
  '''
  A routing path component pattern, which will match against a single component of a requested path.
  '''
  name: str # The name of the pattern, which will be used as the key in the path_params dict for the matched value.
  kind: ConverterKind
  is_opt: bool # Whether this pattern is optional. If True, this pattern will match an empty string.
  prefix: str # A string that must be a prefix of the path component for this pattern to match.
  suffix: str # A string that must be a suffix of the path component for this pattern to match.
  chars: frozenset[str] # The set of characters that are allowed in this pattern.
  #^ The empty set implies all characters are allowed. This is used to ensure that routes do not overlap.
  pattern: Pattern # A compiled regular expression pattern that matches the allowed characters for this pattern.
  ctor: Callable[[str],Any] # A constructor function that converts a string to the appropriate type for this pattern.

  def __init__(self, name:str, kind:ConverterKind, is_opt:bool, prefix:str, suffix:str) -> None:
    self.name = name
    self.kind = kind
    self.is_opt = is_opt
    self.prefix = prefix
    self.suffix = suffix

    if '{' in prefix or '}' in prefix: raise ValueError(f'Invalid pattern: prefix cannot contain braces: {prefix!r}.')
    if '{' in suffix or '}' in suffix: raise ValueError(f'Invalid pattern: suffix cannot contain braces: {suffix!r}.')

    self.chars, self.pattern, self.ctor = converter_kind_attrs[kind]


  @classmethod
  def parse(cls, text:str) -> Self:

    start_idx = text.index('{')
    end_idx = text.index('}')
    #^ These raise ValueError if either brace is not found.

    prefix = text[:start_idx]
    suffix = text[end_idx+1:]
    pattern_text = text[start_idx+1:end_idx]

    name, colon, kind = pattern_text.partition(':')
    if not colon:
      kind = 'str'
    elif not kind:
      raise ValueError(f'Invalid route pattern component: no converter kind following colon: {text!r}.')

    is_opt = False
    if kind.endswith('?'):
      is_opt = True
      kind = kind[:-1]

    if kind not in converter_kinds:
      raise ValueError(f'Unsupported route parameter type: {kind!r} in pattern component: {text!r}.')

    return cls(name=name,kind=cast(ConverterKind, kind), is_opt=is_opt, prefix=prefix, suffix=suffix)


  def match(self, path:list[str], idx:int) -> Any:
    '''
    Attempt to match this pattern against the given path component string.
    If the match is successful, return the value of the path component converted to the appropriate type.
    If the match fails, return None.
    '''

    if self.kind == 'path': # 'path' matches the remainder of the path.
      text = '/'.join(path[idx:])
    else:
      text = path[idx]

    if self.prefix:
      if not text.startswith(self.prefix): return None
      text = text.removeprefix(self.prefix)
    if self.suffix:
      if not text.endswith(self.suffix): return None
      text = text.removesuffix(self.suffix)

    if self.pattern.fullmatch(text):
      return self.ctor(text)

    return None


V = TypeVar('V')

class RouteTree(Generic[V]):
  '''
  A generic prefix tree that maps URL path patterns to values of type V.
  Each node may have a value associated with it.
  '''

  def __init__(self) -> None:
    self.value: V|None = None
    self.fixed: dict[str, RouteTree[V]] = {}
    self.pattern_tree_pairs: list[tuple[RouteComponentPattern, RouteTree[V]]] = []


  def insert(self, path:str, value:V) -> None:
    if not path.startswith('/'):
      raise ValueError(f'Route pattern must start with a slash: {path!r}.')
    path_orig = path
    path = path.removeprefix('/')
    components = path.split('/')
    self._insert(components, 0, value, orig_path=path_orig)


  def _insert(self, components:list[str], idx:int, value:V, orig_path:str) -> None:
    'Recursively insert the given value into the tree at the given path components.'
    comp = components[idx]
    if not comp:
      raise ValueError(f'Invalid route pattern: empty path component in pattern: {orig_path!r}.')

    is_last = (idx == len(components) - 1)

    if is_pattern_route(comp):
      pattern = RouteComponentPattern.parse(comp)
      if pattern.kind == 'path' and not is_last:
        raise ValueError(f'Path pattern {comp!r} must be the last component in route: {orig_path!r}.')
      # Check if an equivalent pattern already exists.
      subtree: RouteTree[V]|None = None
      for existing_pattern, existing_subtree in self.pattern_tree_pairs:
        if (existing_pattern.name == pattern.name and existing_pattern.kind == pattern.kind
            and existing_pattern.prefix == pattern.prefix and existing_pattern.suffix == pattern.suffix):
          subtree = existing_subtree
          break
      if subtree is None:
        _validate_pattern_overlap(pattern, self.pattern_tree_pairs, orig_path)
        subtree = RouteTree()
        self.pattern_tree_pairs.append((pattern, subtree))
    else:
      subtree = self.fixed.get(comp)
      if subtree is None:
        subtree = RouteTree()
        self.fixed[comp] = subtree

    if is_last:
      if subtree.value is not None:
        raise ValueError(f'Duplicate route: {orig_path!r}.')
      subtree.value = value
    else:
      subtree._insert(components, idx + 1, value, orig_path)


  def finalize(self) -> None:
    'Sort pattern_tree_pairs by prefix length descending and recurse into all children.'
    self.pattern_tree_pairs.sort(key=lambda pair: (len(pair[0].prefix), pair[0].prefix, pair[0].kind), reverse=True)
    for subtree in self.fixed.values():
      subtree.finalize()
    for _, subtree in self.pattern_tree_pairs:
      subtree.finalize()


  def get(self, path:str) -> tuple[V,dict[str,Any]]|None:
    path = path.removeprefix('/')
    components = path.split('/')
    return self._get(components, 0, {})


  def _get(self, components:list[str], idx:int, path_params:dict[str,Any]) -> tuple[V,dict[str,Any]]|None:
    '''
    Recursively traverse the tree to find the value that matches the given path components.
    `path_params` is a dictionary that is populated with the values of any matched pattern components as the tree is traversed.
    '''

    if idx >= len(components):
      if self.value is not None:
        return (self.value, path_params)
      return None

    comp = components[idx]

    # Try fixed routes first.
    if (fixed_subtree := self.fixed.get(comp)) is not None:
      result = fixed_subtree._get(components, idx + 1, path_params)
      if result is not None:
        return result

    # Try pattern routes.
    for pattern, subtree in self.pattern_tree_pairs:
      value = pattern.match(components, idx)
      if value is None:
        continue
      path_params[pattern.name] = value
      if pattern.kind == 'path':
        if subtree.value is not None:
          return (subtree.value, path_params)
      else:
        result = subtree._get(components, idx + 1, path_params)
        if result is not None:
          return result
      del path_params[pattern.name] # Backtrack.

    return None


def build_route_tree(routes:dict[str,V]) -> tuple[dict[str,V],RouteTree[V]]:
  '''
  Convert a dict of { path_pattern : value } into (fixed_routes, pattern_tree).
  `fixed_routes` is a dictionary of { path : value } for all paths that uniquely map to a value.
  `pattern_tree` is a path component prefix tree.
  '''

  fixed_routes:dict[str,V] = {}
  pattern_tree:RouteTree[V] = RouteTree()

  for (path, value) in routes.items():
    if is_pattern_route(path):
      pattern_tree.insert(path, value)
    else:
      if path in fixed_routes:
        raise ValueError(f'Route path {path!r} is not unique.')
      fixed_routes[path] = value

  pattern_tree.finalize()
  return fixed_routes, pattern_tree


def _validate_pattern_overlap[V](new:RouteComponentPattern, existing:list[tuple[RouteComponentPattern, RouteTree[V]]],
 orig_path:str) -> None:
  'Validate that the new pattern does not overlap with any existing pattern in the same prefix group.'

  for existing_pattern, _ in existing:
    if existing_pattern.prefix != new.prefix:
      continue
    if not new.chars or not existing_pattern.chars: # Empty chars means all characters allowed.
      raise ValueError(
        f'Overlapping route patterns: {new.name!r} and {existing_pattern.name!r} both match all characters'
        f' with prefix {new.prefix!r} in route: {orig_path!r}.')
    overlap = new.chars & existing_pattern.chars
    if overlap:
      overlap_str = ''.join(sorted(overlap))
      raise ValueError(
        f'Overlapping route patterns: {new.name!r} and {existing_pattern.name!r} share characters'
        f' {overlap_str!r} with prefix {new.prefix!r} in route: {orig_path!r}.')


def is_pattern_route(path:str) -> bool:
  return '{' in path or '}' in path
