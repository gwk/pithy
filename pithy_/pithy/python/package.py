# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Python module resolution and package discovery.

Resolve filesystem targets and dotted module names, discover package roots, and walk Python source files.
Environment-based resolution is static; see `resolve_module_installed` for search policy and limitations.
'''

import sys
from importlib.machinery import (BYTECODE_SUFFIXES, EXTENSION_SUFFIXES, ExtensionFileLoader, FileFinder, ModuleSpec, PathFinder,
  SOURCE_SUFFIXES, SourceFileLoader, SourcelessFileLoader)
from os import environ
from typing import Callable, Iterable, Iterator

from ..filestatus import is_dir, is_file, is_link
from ..fs import abs_path, list_dir, path_exists, path_join, real_path, walk_dirs_up, walk_files
from ..path import norm_path, path_dir, path_name


_context_keywords_ = ['PYTHONSAFEPATH', 'discovery', 'find_spec', 'importlib', 'module name', 'module path', 'package root',
  'pkgutil', 'py.typed', 'resolve', 'sys.path', 'walk']


target_resolution_help = '''
Dotted module names resolve through the running Python environment without loading target modules or their parents.
Resolution is static: dynamic package paths, custom submodule finders, and source inside archives are unsupported.
'''

safe_path_help = '''
-P or a nonempty PYTHONSAFEPATH enables safe-path mode, omitting the implicit Python search directory.
Explicit PYTHONPATH entries remain searchable; Python's -E and -I ignore PYTHONSAFEPATH.
Explicit paths still work in safe-path mode: use ./pkg to select a local directory instead of the module name pkg.
'''


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


def module_name_for_path(path:str) -> tuple[str,str]:
  '''
  Derive the dotted module name for a Python file by walking up through package directories (those containing __init__.py).
  Returns (module name, search dir), where the search dir is the parent of the topmost package directory.
  '''
  path = abs_path(path)
  dir = path_dir(path)
  parts = [path_name(path).removesuffix('.py')]
  while path_exists(path_join(dir, '__init__.py'), follow=True):
    parts.append(path_name(dir))
    parent = path_dir(dir)
    if parent == dir: break
    dir = parent
  parts.reverse()
  if len(parts) > 1 and parts[-1] == '__init__': parts.pop()
  return '.'.join(parts), dir


def resolve_module_in_dirs(name:str, search_dirs:Iterable[str]) -> str|None:
  '''
  Resolve a dotted name within explicit filesystem roots without loading modules.
  Select each package before searching its children; regular packages shadow later copies.
  Namespace portions are combined, and packages take precedence over same-named module files.
  Native and bytecode-only modules can shadow source files, but return None.
  '''
  parts = name.split('.')
  if not all(parts): return None
  locations = list(search_dirs)
  for idx in range(len(parts)):
    spec = _find_spec_in_dirs('.'.join(parts[:idx+1]), locations)
    if spec is None: return None
    if idx == len(parts)-1: return _source_path(spec)
    if spec.submodule_search_locations is None: return None
    locations = list(spec.submodule_search_locations)
  return None


def resolve_module_installed(name:str, *, safe_path:bool=False) -> str|None:
  '''
  Resolve a dotted name in the running Python environment without loading target modules or their parents.
  `safe_path=True` acts like Python's `-P`: omit the interpreter's automatically prepended search directory.
  Python's own safe-path flag and nonempty PYTHONSAFEPATH are also respected; -E/-I ignore the environment variable.
  Explicit entries from PYTHONPATH or installation configuration remain searchable, even if they name the current directory.
  This assumes sys.path still has its interpreter-initialized leading entry when Python was started without -P.

  Consult top-level meta-path finders in their registered order, including editable-install finders.
  Finders execute their lookup code, but this function never invokes loaders or imports target packages.
  Resolve descendants statically within the selected package's filesystem locations.
  Package initialization that changes __path__, custom submodule finders, and source inside archives are not supported.
  Returns None for unresolved names, namespace packages themselves, and modules without a regular Python source file.
  '''
  if not name or not all(name.split('.')): return None
  search_dirs = list(sys.path)
  if _safe_path_enabled(safe_path) and not sys.flags.safe_path:
    search_dirs = search_dirs[1:]
  top, _, rest = name.partition('.')
  spec = None
  for finder in sys.meta_path:
    try:
      spec = finder.find_spec(top, search_dirs if finder is PathFinder else None)
    except (ImportError, ValueError): return None
    if spec is not None: break
  if spec is None: return None
  if not rest: return _source_path(spec)
  if spec.submodule_search_locations is None: return None
  return resolve_module_in_dirs(rest, spec.submodule_search_locations)


def resolve_spec_paths(spec:str, resolve_module:Callable[[str],str|None]|None=None, *, safe_path:bool=False) -> list[str]:
  '''
  Resolve a target spec to a sorted list of Python file paths.
  A spec is interpreted as a path if it ends in `.py`, contains a slash, or is `.` or `..`.
  Outside safe-path mode, other existing filesystem entries are also interpreted as paths.
  Otherwise it is treated as a dotted module name and resolved with `resolve_module`,
  which defaults to `resolve_module_installed` with the given `safe_path` setting.
  Safe-path mode follows `resolve_module_installed`; explicit paths remain usable in that mode.
  A custom resolver is responsible for its own module search policy.
  A dotted name that resolves to a package `__init__` file includes all of the package's submodule files.
  Raises SpecResolutionError if the spec cannot be resolved to any Python files.
  '''
  is_path = spec.endswith('.py') or '/' in spec or spec in ('.', '..')
  if is_path or (not _safe_path_enabled(safe_path) and path_exists(spec, follow=True)):
    try: paths = sorted(walk_files(spec, file_exts=['.py']))
    except FileNotFoundError: raise SpecResolutionError(f'target path not found: {spec!r}') from None
    if not paths: raise SpecResolutionError(f'target path contains no Python files: {spec!r}')
    return paths
  mod_path = resolve_module(spec) if resolve_module is not None else resolve_module_installed(spec, safe_path=safe_path)
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


def _safe_path_enabled(safe_path:bool) -> bool:
  return safe_path or sys.flags.safe_path or (not sys.flags.ignore_environment and bool(environ.get('PYTHONSAFEPATH')))


def _source_path(spec:ModuleSpec) -> str|None:
  origin = spec.origin
  return origin if origin and origin.endswith('.py') and is_file(origin, follow=True) else None


def _find_spec_in_dirs(name:str, search_dirs:Iterable[str]) -> ModuleSpec|None:
  # FileFinder returns plain namespace locations without requiring parent packages in sys.modules.
  namespaces:list[str] = []
  for directory in search_dirs:
    finder = FileFinder(directory or '.', (ExtensionFileLoader, EXTENSION_SUFFIXES), (SourceFileLoader, SOURCE_SUFFIXES),
      (SourcelessFileLoader, BYTECODE_SUFFIXES))
    spec = finder.find_spec(name)
    if spec is None: continue
    if spec.loader is not None: return spec
    if spec.submodule_search_locations is not None: namespaces.extend(spec.submodule_search_locations)
  if not namespaces: return None
  spec = ModuleSpec(name, loader=None, is_package=True)
  spec.submodule_search_locations = namespaces
  return spec
