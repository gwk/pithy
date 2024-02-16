# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re as _re
from itertools import zip_longest as _zip_longest
from os import fspath as _fspath, PathLike
from os.path import (abspath as _abspath, basename as _basename, commonpath as _commonpath, dirname as _dirname,
  expanduser as _expand_user, isabs as _isabs, join as _join, realpath as _realpath, relpath as _relpath, split as _split)


Path = str|PathLike
PathOrFd = Path|int


class AbsolutePathError(Exception): pass
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
  import __main__
  path = __main__.__file__
  if not path: raise Exception('could not determine executable path.')
  return _realpath(path)


def expand_user(path:Path) -> str:
  return _expand_user(path)


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
  try: return _commonpath([str_path(p) for p in paths])
  except ValueError: # we want a more specific exception.
    raise MixedAbsoluteAndRelativePathsError(paths) from None


def path_compound_ext(path: Path) -> str:
  return ''.join(path_exts(path))


def path_descendants(start_path: Path, end_path: Path, include_start=True, include_end=True) -> tuple[str, ...]:
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
    return (str_path(start_path),) if include_start or include_end else ()
  if prefix != comps[:len(prefix)]:
    raise PathIsNotDescendantError(end_path, start_path)
  start_i = len(prefix) + (0 if include_start else 1)
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


def path_exts(path: Path) -> tuple[str, ...]:
  exts = []
  while True:
    path, ext = split_stem_ext(path)
    if not ext: break
    exts.append(ext)
  return tuple(exts)


def path_join(first: Path, *subsequent: Path) -> str:
  '''
  Join the paths using the system path separator.
  Unlike `os.path.join`, this implementation does not allow subsequent absolute paths to replace the preceding path.
  Currently it does not allow absolute paths at all.
  TODO: perhaps we should join subsequent absolute paths as if they were relative?
  '''
  for p in subsequent:
    if is_path_abs(p): raise AbsolutePathError(p)
  return _join(str_path(first), *[str_path(p) for p in subsequent])


def path_name(path: Path) -> str:
  "Return the name portion of a path (possibly including an extension); the 'basename' in Unix terminology."
  return _basename(str_path(path))


def path_name_stem(path: Path) -> str:
  'The file name without extension; the name stem will not span directories.'
  return path_stem(path_name(path))


def path_rel_to_dir(path:Path, dir:Path) -> str:
  comps:list[str] = []
  parent_comps = 0
  for p, r in _zip_longest(path_split(abs_path(path)), path_split(abs_path(dir))):
    if not parent_comps and p == r: continue
    if p is not None: comps.append(p)
    if r is not None: parent_comps += 1
  comps = ['..']*parent_comps + comps
  if not comps: return '.'
  return path_join(*comps)


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


def path_split(path: Path) -> list[str]:
  # TODO: rename to path_comps?
  np = norm_path(path)
  if np == '/': return ['/']
  assert not np.endswith('/')
  return [comp or '/' for comp in np.split('/')]


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


def split_dir_name(path: Path) -> tuple[str, str]:
  "Split the path into dir and name (possibly including an extension) components, e.g. 'dir/name'."
  return _split(str_path(path))


def split_dir_stem_ext(path: Path) -> tuple[str, str, str]:
  'Split the path into a (dir, stem, ext) triple.'
  dir, name = split_dir_name(path)
  stem, ext = split_stem_ext(name)
  return dir, stem, ext


def split_stem_ext(path: Path) -> tuple[str, str]:
  '''
  Split `path` into (stem, extension) components.
  'stem.ext' -> ('stem', '.ext').
  'stem.ext.ext' -> ('stem.ext', '.ext').
  The stem can include slashes. The extension may be empty.
  Extension is everything from the last dot to the end, ignoring leading dots in the file name.
  It is always true that `path == root + ext`.
  '''
  path = str_path(path)
  slash_idx = path.rfind('/') # -1 if not found.
  dot_idx = path.rfind('.') # -1 if not found.
  if slash_idx < dot_idx: # Found a dot after the last slash, if any slash exists. Skip all leading dots in the name.
    name_idx = slash_idx + 1 # Start of the file name.
    while name_idx < dot_idx:
      if path[name_idx] != '.': # Found a non-dot character in the name.
        return path[:dot_idx], path[dot_idx:]
      name_idx += 1 # Skip the dot.
  return path, ''


def split_stem_multi_ext(path: Path) -> tuple[str, str]:
  '''
  Split `path` into (stem, multi-extension) components.
  'stem.ext' -> ('stem', '.ext').
  'stem.ext.ext' -> ('stem', '.ext.ext').
  The stem can include slashes. The extension may be empty.
  The multi-extension is everything from the first dot in the file name to the end, ignoring leading dots in the file name.
  It is always true that `path == root + ext`.
  '''
  path = str_path(path)
  slash_idx = path.rfind('/') # -1 if not found.
  name_idx = slash_idx + 1 # Start of the file name.
  dot_find_start_idx = name_idx
  while dot_find_start_idx < len(path) and path[dot_find_start_idx] == '.': # Skip leading dots in the file name.
    dot_find_start_idx += 1
  dot_idx = path.find('.', dot_find_start_idx)
  if dot_idx == -1: return path, ''
  return path[:dot_idx], path[dot_idx:]


def str_path(path:Path) -> str:
  p = _fspath(path)
  if isinstance(p, str): return p
  assert isinstance(p, bytes)
  return p.decode()


def vscode_path(path:str) -> str:
  'VSCode will only recognize source locations if the path contains a slash; add "./" to plain file names.'
  if '/' in path or path.startswith('<') and path.endswith('>'): return path # Do not alter pseudo-names like <stdin>.
  return './' + path
