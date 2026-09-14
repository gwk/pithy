# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, Iterable, Iterator

from ..filestatus import is_dir, is_file, is_link
from ..fs import abs_path, list_dir, path_exists, path_join, real_path, walk_dirs_up, walk_files
from ..path import norm_path, path_dir


class SpecResolutionError(Exception):
  'A target spec could not be resolved to Python files.'


def walk_module_paths(*paths:str, exclude_dirs:Iterable[str]=()) -> Iterator[str]:
  '''
  Yield Python source file paths recursively without importing modules or resolving dependencies.
  Inputs are files or directories; directory trees need not contain package markers such as __init__.py.
  Includes private modules, scripts and tests. Paths are normalized, and directory entries are sorted.
  Overlapping inputs are deduplicated by real path. Explicit input files must have the .py suffix.
  Skip discovered symlinks, hidden names, __pycache__, virtual environments with pyvenv.cfg,
  and directories whose names are in `exclude_dirs`. Explicit input roots are not excluded.
  Filesystem errors propagate.
  '''
  excluded = frozenset(exclude_dirs) | {'__pycache__'}
  seen:set[str] = set()

  def walk(path:str) -> Iterator[str]:
    real = real_path(path)
    if real in seen: return
    seen.add(real)
    if is_dir(path, follow=True):
      for name in list_dir(path):
        child = path_join(path, name)
        if is_link(child): continue
        if is_dir(child, follow=False):
          if name in excluded or is_file(path_join(child, 'pyvenv.cfg'), follow=False): continue
          yield from walk(child)
        elif name.endswith('.py') and is_file(child, follow=False):
          yield from walk(child)
    elif is_file(path, follow=True):
      if not path.endswith('.py'): raise ValueError(f'not a Python source file: {path!r}')
      yield path
    else:
      raise FileNotFoundError(path)

  for path in paths:
    yield from walk(norm_path(path))


def find_package_root(path:str, *, package_roots:set[str]|None=None) -> str|None:
  '''
  Find the package root directory for a Python source file or directory.
  Walks up from `path` searching for a py.typed marker file (PEP 561).
  The search is bounded by the filesystem root, and by the first ancestor that cannot be traversed.
  Returns the directory containing py.typed, or None if no such directory is found.
  If `package_roots` is provided, any directory whose absolute path is in that set is also a stop condition.
  '''
  abs_roots = {abs_path(r) for r in package_roots} if package_roots else set()
  for dir_path in walk_dirs_up(abs_path(path), top='/', include_top=True):
    try:
      if path_exists(path_join(dir_path, 'py.typed'), follow=False): return dir_path
    except PermissionError: break # An ancestor that we cannot traverse bounds the search.
    if dir_path in abs_roots: return dir_path
  return None


def resolve_module_in_dirs(name:str, search_dirs:Iterable[str]) -> str|None:
  'Resolve a dotted module name to a file path by searching `search_dirs`; returns None if not found.'
  if not name: return None
  rel = name.replace('.', '/')
  for search_dir in search_dirs:
    base = path_join(search_dir, rel)
    for cand in (base + '.py', path_join(base, '__init__.py')):
      if path_exists(cand, follow=True): return cand
  return None


def resolve_spec_paths(spec:str, resolve_module:Callable[[str],str|None]|None=None) -> list[str]:
  '''
  Resolve a target spec to a sorted list of Python file paths.
  A spec is interpreted as a path if it ends in `.py`, contains a slash, or exists on the filesystem;
  otherwise it is treated as a dotted module name and resolved with `resolve_module`,
  which defaults to a search of the current directory.
  A dotted name that resolves to a package `__init__` file includes all of the package's submodule files.
  Raises SpecResolutionError if the spec cannot be resolved to any Python files.
  '''
  if spec.endswith('.py') or '/' in spec or path_exists(spec, follow=True):
    try: paths = sorted(walk_files(spec, file_exts=['.py']))
    except FileNotFoundError: raise SpecResolutionError(f'target path not found: {spec!r}') from None
    if not paths: raise SpecResolutionError(f'target path contains no Python files: {spec!r}')
    return paths
  mod_path = resolve_module(spec) if resolve_module is not None else resolve_module_in_dirs(spec, ('.',))
  if mod_path is None: raise SpecResolutionError(f'cannot resolve module {spec!r}.')
  if mod_path.endswith('__init__.py'): # A package spec includes all of its submodules.
    return sorted(walk_files(path_dir(mod_path), file_exts=['.py']))
  return [mod_path]


def qualname_rel_to(base:str, qual:str) -> str:
  '''
  Calculate the possibly-relative dotted name for `qual` as seen from the module `base`.
  If the two names share no leading parts, `qual` is returned unchanged.
  Otherwise the shared prefix is replaced with relative-import dots using plain module semantics,
  where one dot refers to the package containing `base`: `qualname_rel_to('a.b', 'a.c.d') == '.c.d'`.
  If `base` is a package (an `__init__` file), an actual relative import would need one more leading dot;
  this function cannot distinguish that case and always uses the plain module interpretation.
  A name within `base` itself is rendered with a single dot: `qualname_rel_to('a.b', 'a.b.x') == '.x'`.
  '''
  base_parts = base.split('.')
  qual_parts = qual.split('.')
  common = 0
  for b, q in zip(base_parts, qual_parts):
    if b != q: break
    common += 1
  if not common: return qual
  dots = max(1, len(base_parts) - common)
  return '.'*dots + '.'.join(qual_parts[common:])
