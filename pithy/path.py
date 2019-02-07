# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re as _re
import shutil as _shutil
import stat as _stat
import time as _time

from itertools import zip_longest as _zip_longest
from os import (
  DirEntry,
  PathLike,
  fspath as _fspath,
  get_exec_path as _get_exec_path,
  scandir as _scandir,
  sep
)
from os.path import (
  abspath as _abspath,
  basename as _basename,
  commonpath as _commonpath,
  dirname as _dirname,
  exists as _exists,
  isabs as _isabs,
  join as _join,
  realpath as _realpath,
  relpath as _relpath,
  split as _split,
  splitext as _splitext,
)
from typing import AbstractSet, Any, FrozenSet, IO, Iterable, Iterator, List, Optional, Pattern, TextIO, Tuple, Union


Path = Union[str, PathLike]
PathOrFd = Union[Path, int]


class MixedAbsoluteAndRelativePathsError(Exception): pass
class NotAPathError(Exception): pass
class PathIsNotDescendantError(Exception): pass


def abs_or_norm_path(path: Path, make_abs: bool) -> str:
  'Return the absolute path if make_abs is True. If make_abs is False, return a normalized path.'
  return abs_path(path) if make_abs else norm_path(path)


def abs_path(path: Path) -> str:
  'Return the absolute path corresponding to `path`.'
  return _abspath(norm_path(path))


def current_dir() -> str: return abs_path('.')


def executable_dir() -> str:
  'Return the parent directory of this excutable.'
  return _dirname(executable_path())


def executable_path() -> str:
  'Return the path to this executable.'
  import __main__ # type: ignore # mypy bug.
  path: str = __main__.__file__
  return _realpath(path)


def insert_path_stem_suffix(path: Path, suffix: str) -> str:
  'Insert a suffix in between the path stem and ext.'
  stem, ext = split_stem_ext(path)
  return f'{stem}{suffix}{ext}'


def is_norm_path(path:Path) -> bool:
  return bool(_norm_path_re.fullmatch(str_path(path)))


_norm_path_re = _re.compile(r'''(?x)
# This is nasty. In particular the "component" clauses have to deal with the validity of three or more dots.
  [./] # Either a lone dot or slash, or...
| (?: # Absolute path.
    / # Leading slash.
    (?:[^./]|\.{1,2}[^./]|\.{3})[^/]* # Component.
  )+
| # Relative path.
  (?: \.\./ )* # Leading backups ending with a slash.
  (?:
    \.\. # Final backup.
  | (?:[^./]|\.{1,2}[^./]|\.{3})[^/]* # Initial component.
    (?: / (?:[^./]|\.{1,2}[^./]|\.{3})[^/]* )* # Trailing components.
  )
''')


def is_path_abs(path: Path) -> bool:
  'Return true if `path` is an absolute path.'
  return _isabs(path)


def is_sub_path(path: Path) -> bool:
  'Return true if `path` is a relative path that, after normalization, does not refer to parent directories.'
  return not is_path_abs(path) and '..' not in path_split(path)



def norm_path(path:Path) -> str:
  '''
  Normalize `path`.
  * trailing slashes are removed.
  * duplicate slashes (empty components) and '.' components are removed.
  * '..' components are simplified, or dropped if it implies a location beyond the root '/'.
  * Unlike `os.path.normpath`, this implementation simplifies leading double slash to a single slash.
  '''
  p = str_path(path)
  lead_slash = '/' if p.startswith('/') else ''
  comps:list = []
  for comp in p.split('/'):
    if not comp or comp == '.': continue
    if comp == '..':
      if comps:
        if comps[-1] == '..': comps.append(comp)
        else: comps.pop()
      else:
        if lead_slash: pass # '..' beyond root gets dropped.
        else: comps.append(comp)
    else:
      comps.append(comp)
  return (lead_slash + '/'.join(comps)) or '.'


def parent_dir() -> str: return abs_path('..')


def path_common_prefix(*paths: Path) -> str:
  'Return the common path prefix for a sequence of paths.'
  try: return _commonpath([str_path(p) for p in paths]) # type: ignore
  except ValueError: # we want a more specific exception.
    raise MixedAbsoluteAndRelativePathsError(paths) from None


def path_compound_ext(path: Path) -> str:
  return ''.join(path_exts(path))


def path_descendants(start_path: Path, end_path: Path, include_start=True, include_end=True) -> Tuple[str, ...]:
  '''
  Return a tuple of paths from `start_path` to `end_path`.
  By default, `include_start` and `include_end` are both True.
  TODO: normalize paths, and deal with '..' case.
  '''
  prefix = path_split(start_path)
  comps = path_split(end_path)
  if not prefix: raise NotAPathError(start_path)
  if not comps: raise NotAPathError(end_path)
  if prefix == comps:
    if include_start or include_end:
      return (str_path(start_path),)
    return ()
  if prefix != comps[:len(prefix)]:
    raise PathIsNotDescendantError(end_path, start_path)
  start_i = len(prefix) + (1 if include_start else 0)
  end_i = len(comps) + (1 if include_end else 0)
  return tuple(path_join(*comps[:i]) for i in range(start_i, end_i))


def path_dir(path: Path) -> str:
  "Return the dir portion of `path` (possibly empty), e.g. 'dir/name'."
  return _dirname(str_path(path))


def path_dir_or_dot(path: Path) -> str:
  "Return the dir portion of a path, e.g. 'dir/name', or '.' in the case of no path."
  return path_dir(path) or '.'


def path_ext(path: Path) -> str:
  'The file extension of the path.'
  return split_stem_ext(path)[1]


def path_exts(path: Path) -> Tuple[str, ...]:
  exts = []
  while True:
    path, ext = split_stem_ext(path)
    if not ext: break
    exts.append(ext)
  return tuple(exts)


def path_for_cmd(cmd: str) -> Optional[str]:
  for dir in _get_exec_path():
    try: entries = _scandir(dir)
    except FileNotFoundError: continue # directory in PATH might not exist.
    for entry in entries:
      if entry.name == cmd and entry.is_file: return path_join(dir, cmd)
  return None


def path_join(first: Path, *additional: Path) -> str:
  'Join the path with the system path separator.'
  return _join(str_path(first), *[str_path(p) for p in additional])


def path_name(path: Path) -> str:
  "Return the name portion of a path (possibly including an extension); the 'basename' in Unix terminology."
  return _basename(str_path(path))


def path_name_stem(path: Path) -> str:
  'The file name without extension; the name stem will not span directories.'
  return path_stem(path_name(path))


def path_rel_to_ancestor(path: Path, ancestor: str, dot=False) -> str:
  '''
  Return the path relative to `ancestor`.
  If `path` is not descended from `ancestor`, raise PathIsNotDescendantError.
  If `path` and `ancestor` are equivalent (path component-wise),
   then return '.' if dot is True, or else raise PathIsNotDescendantError.
  '''
  comps = path_split(path)
  prefix = path_split(ancestor)
  if comps == prefix:
    if dot: return '.'
    raise PathIsNotDescendantError(path, ancestor)
  if prefix == comps[:len(prefix)]:
    return path_join(*comps[len(prefix):])
  raise PathIsNotDescendantError(path, ancestor)


def path_rel_to_ancestor_or_abs(path: Path, ancestor: str, dot=False) -> str:
  '''
  Return the path relative to `ancestor` if `path` is a descendant,
  or else the corresponding absolute path.
  `dot` has the same effect as in `path_rel_to_ancestor`.
  '''
  ap = abs_path(path)
  aa = abs_path(ancestor)
  try:
    return path_rel_to_ancestor(ap, aa, dot=dot)
  except PathIsNotDescendantError:
    return ap


def path_rel_to_current_or_abs(path: Path, dot=False) -> str:
  return path_rel_to_ancestor_or_abs(path, current_dir(), dot=dot)


def path_split(path: Path) -> List[str]:
  # TODO: rename to path_comps?
  np = norm_path(path)
  if np == '/': return ['/']
  assert not np.endswith('/')
  return [comp or '/' for comp in np.split(sep)]


def path_stem(path: Path) -> str:
  'The path without the file extension; the stem may span multiple directories.'
  return split_stem_ext(path)[0]


def rel_path(path: Path, start: Path='.') -> str:
  'Return a version of `path` relative to `start`, which defaults to the current directory.'
  return _relpath(str_path(path), str_path(start))


def replace_first_dir(path: Path, replacement: str) -> str:
  parts = path_split(path)
  if not parts: raise Exception('replace_first_dir: path is empty')
  parts[0] = replacement
  return path_join(*parts)


def split_dir_name(path: Path) -> Tuple[str, str]:
  "Split the path into dir and name (possibly including an extension) components, e.g. 'dir/name'."
  return _split(str_path(path))


def split_dir_stem_ext(path: Path) -> Tuple[str, str, str]:
  'Split the path into a (dir, stem, ext) triple.'
  dir, name = split_dir_name(path)
  stem, ext = split_stem_ext(name)
  return dir, stem, ext


def split_stem_ext(path: Path) -> Tuple[str, str]:
  '''
  Split the path into stem (possibly spanning directories) and extension components, e.g. 'stem.ext'.
  '''
  return _splitext(str_path(path))


def str_path(path: Path) -> str:
  p = _fspath(path)
  if isinstance(p, str): return p
  assert isinstance(p, bytes)
  return p.decode()
