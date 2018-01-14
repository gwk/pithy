# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os as _os
import os.path as _path
import re as _re
import shutil as _shutil
import stat as _stat
import time as _time

from itertools import zip_longest as _zip_longest
from typing import AbstractSet, Any, FrozenSet, IO, Iterable, Iterator, List, Optional, TextIO, Tuple, Union
from typing.re import Pattern # type: ignore


Path = Union[str, _os.PathLike]
PathOrFd = Union[Path, int]

class NotAPathError(Exception): pass
class PathIsNotDescendantError(Exception): pass
class PathHasNoDirError(Exception): pass
class MixedAbsoluteAndRelativePathsError(Exception): pass


# paths.

def _str_for(path: Path) -> str:
  if isinstance(path, str): return path
  p = path.__fspath__()
  if isinstance(path, str): return p
  assert isinstance(p, bytes)
  return p.decode()


def executable_path() -> str:
  'Return the path to this executable.'
  import __main__ # type: ignore # mypy bug.
  path: str = __main__.__file__
  return _path.realpath(path)

def executable_dir() -> str:
  'Return the parent directory of this excutable.'
  return _path.dirname(executable_path())

def is_path_abs(path: Path) -> bool:
  'Return true if `path` is an absolute path.'
  return _path.isabs(path)

def is_sub_path(path: Path) -> bool:
  'Return true if `path` is a relative path that does not refer to parent directories.'
  return not is_path_abs(path) and '..' not in path_split(path)

def norm_path(path: Path) -> str:
  'Normalize `path` according to system convention.'
  return _path.normpath(_str_for(path))

def rel_path(path: Path, start: Path='.') -> str:
  'Return a version of `path` relative to `start`, which defaults to the current directory.'
  return _path.relpath(_str_for(path), _str_for(start))

def path_common_prefix(*paths: Path) -> str:
  'Return the common path prefix for a sequence of paths.'
  try: return _path.commonpath([_str_for(p) for p in paths])
  except ValueError: # we want a more specific exception.
    raise MixedAbsoluteAndRelativePathsError(paths) from None

def path_dir(path: Path) -> str:
  "Return the dir portion of `path` (possibly empty), e.g. 'dir/name'."
  return _path.dirname(_str_for(path))

def path_dir_or_dot(path: Path) -> str:
  "Return the dir portion of a path, e.g. 'dir/name', or '.' in the case of no path."
  return path_dir(path) or '.'

def path_for_cmd(cmd: str) -> Optional[str]:
  for dir in _os.get_exec_path():
    try: entries = _os.scandir(dir)
    except FileNotFoundError: continue # directory in PATH might not exist.
    for entry in entries:
      if entry.name == cmd and entry.is_file: return path_join(dir, cmd)
  return None

def path_join(first: Path, *additional: Path) -> str:
  'Join the path with the system path separator.'
  return _path.join(_str_for(first), *[_str_for(p) for p in additional])

def path_name(path: Path) -> str:
  "Return the name portion of a path (possibly including an extension), e.g. 'dir/name'."
  return _path.basename(_str_for(path))

def path_split(path: Path) -> List[str]:
  # TODO: rename to path_comps?
  np = norm_path(path)
  if np == '/': return ['/']
  assert not np.endswith('/')
  return [comp or '/' for comp in np.split(_os.sep)]

def path_stem(path: Path) -> str:
  'The path without the file extension; the stem may span multiple directories.'
  return split_stem_ext(path)[0]

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

def path_compound_ext(path: Path) -> str:
  return ''.join(path_exts(path))

def path_name_stem(path: Path) -> str:
  'The file name without extension; the name stem will not span directories.'
  return path_stem(path_name(path))

def replace_first_dir(path: Path, replacement: str) -> str:
  parts = path_split(path)
  if not parts: raise Exception('replace_first_dir: path is empty')
  parts[0] = replacement
  return path_join(*parts)

def split_dir_name(path: Path) -> Tuple[str, str]:
  "Split the path into dir and name (possibly including an extension) components, e.g. 'dir/name'."
  return _path.split(path)

def split_dir_stem_ext(path: Path) -> Tuple[str, str, str]:
  'Split the path into a (dir, stem, ext) triple.'
  dir, name = split_dir_name(path)
  stem, ext = split_stem_ext(name)
  return dir, stem, ext

def split_stem_ext(path: Path) -> Tuple[str, str]:
  '''
  Split the path into stem (possibly spanning directories) and extension components, e.g. 'stem.ext'.
  '''
  return _path.splitext(_str_for(path))

def append_path_stem_suffix(path: Path, suffix: str) -> str:
  'Append suffix to the path stem.'
  # TODO: rename to insert_path_stem_suffix?
  stem, ext = split_stem_ext(path)
  return stem + suffix + ext

# file system.

def abs_path(path: Path) -> str:
  'Return the absolute path corresponding to `path`.'
  return _path.abspath(_str_for(path))

def abs_or_norm_path(path: Path, make_abs: bool) -> str:
  'Return the absolute path if make_abs is True. If make_abs is False, return a normalized path.'
  return abs_path(path) if make_abs else norm_path(path)


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


def copy_file(src: str, dst: str, follow_symlinks=True) -> None:
  'Copies file from source to destination.'
  _shutil.copy(src, dst, follow_symlinks=follow_symlinks)


def copy_dir_tree(src: str, dst: str, follow_symlinks=True, preserve_metadata=True, ignore_dangling_symlinks=False) -> None:
  'Copies a directory tree.'
  _shutil.copytree(src, dst,
    symlinks=(not follow_symlinks),
    ignore=None,
    copy_function=(_shutil.copy2 if preserve_metadata else _shutil.copy),
    ignore_dangling_symlinks=ignore_dangling_symlinks)


def expand_user(path: Path) -> str: return _path.expanduser(_str_for(path))

def home_dir() -> str: return _path.expanduser('~')

def is_dir(path: Path) -> bool: return _path.isdir(path)

def is_file(path: Path) -> bool: return _path.isfile(path)

def is_link(path: Path) -> bool: return _path.islink(path)

def is_mount(path: Path) -> bool: return _path.ismount(path)

def link_exists(path: Path) -> bool: return _path.lexists(path)


def list_dir(path: PathOrFd, exts: Iterable[str]=(), hidden=False) -> List[str]:
  exts = normalize_exts(exts)
  names = sorted(_os.listdir(path)) # type: ignore # https://github.com/python/typeshed/issues/1653
  #^ Sort became necessary at some point, presumably for APFS.
  if not exts and hidden: return names # no filtering necessary.
  return [n for n in names if (
    (not exts or path_ext(n) in exts) and (hidden or not n.startswith('.')))]


def list_dir_paths(path: Path, exts: Iterable[str]=(), hidden=False) -> List[str]:
  return [path_join(path, name) for name in list_dir(path, exts=exts, hidden=hidden)]


def make_dir(path: Path) -> None: return _os.mkdir(path)

def make_dirs(path: Path, mode=0o777, exist_ok=True) -> None: return _os.makedirs(path, mode, exist_ok)

def make_link(src: Path, dst: Path, absolute=False, allow_nonexistent=False, make_dirs=False, perms:Optional[int]=None) -> None:
  if perms is not None: raise NotImplementedError # TODO
  if not allow_nonexistent and not path_exists(src):
    raise FileNotFoundError(src)
  if absolute:
    _src = abs_path(src)
  else:
    _src = rel_path(src, start=path_dir(dst))
  if make_dirs:
    _os.makedirs(path_dir(dst), exist_ok=True)
  return _os.symlink(_src, dst)

def path_exists(path: Path) -> bool: return _path.exists(path)

def real_path(path: Path) -> str: return _path.realpath(_str_for(path))

def remove_file(path: Path) -> None: _os.remove(path)

def remove_file_if_exists(path: Path) -> None:
  if is_file(path):
    remove_file(path)

def remove_empty_dir(path: Path) -> None: _os.rmdir(path)

def remove_empty_dirs(path: Path) -> None: _os.removedirs(path)

def current_dir() -> str: return abs_path('.')

def parent_dir() -> str: return abs_path('..')

def change_dir(path: PathOrFd) -> None: _os.chdir(path)

def file_stat(path: PathOrFd) -> _os.stat_result: return _os.stat(path)

def file_inode(path: PathOrFd) -> int: return _os.stat(path).st_ino

def file_time_access(path: PathOrFd) -> float: return _os.stat(path).st_atime

def file_time_mod(path: PathOrFd) -> float: return _os.stat(path).st_mtime

def file_time_mod_or_zero(path: str) -> float:
  try: return file_time_mod(path)
  except FileNotFoundError: return 0

def file_time_meta_change(path: PathOrFd) -> float: return _os.stat(path).st_ctime

def file_size(path: PathOrFd) -> int: return _os.stat(path).st_size

def file_permissions(path: PathOrFd) -> int: return _os.stat(path).st_mode

def is_file_not_link(path: Path) -> bool: return is_file(path) and not is_link(path)

def is_dir_not_link(path: Path) -> bool: return is_dir(path) and not is_link(path)

def is_node_not_link(path: Path) -> bool: return path_exists(path) and not is_link(path)

def is_file_executable_by_owner(path: Path) -> bool: return bool(file_permissions(path) & _stat.S_IXUSR)


def is_python_file(path: Path, always_read=False) -> bool:
  '''
  Guess if a file is a python file, based first on path extension, or if that is not present on shebang line.
  TODO: support more than just '#!/usr/bin/env python'
  TODO: support zip archives?
  '''
  if not always_read:
    ext = path_ext(path)
    if ext: return ext == '.py'
  try:
    with open(path, 'rb') as f:
      expected = b'#!/usr/bin/env python'
      head = f.read(len(expected))
      return bool(head == expected)
  except (FileNotFoundError, IsADirectoryError): return False


def product_needs_update(product=PathOrFd, source=PathOrFd) -> bool:
  return file_time_mod_or_zero(product) <= file_time_mod(source)


def set_file_time_mod(path: PathOrFd, mtime: Optional[float]) -> None:
  '''
  Update the access and modification times of the file at `path`.
  The access time is always updated to the current time;
  `mtime` defaults to the current time.
  '''
  _os.utime(path, None if mtime is None else (_time.time(), mtime))


def add_file_execute_permissions(path: PathOrFd) -> None:
  old_perms = file_permissions(path)
  new_perms = old_perms | _stat.S_IXUSR | _stat.S_IXGRP | _stat.S_IXOTH
  _os.chmod(path, new_perms)

def remove_dir_contents(path: Path) -> None:
  if _path.islink(_str_for(path)): raise Exception(f'remove_dir_contents received symlink: {path}')
  l = _os.listdir(path) # type: ignore # https://github.com/python/typeshed/issues/1653
  for n in l:
    p = path_join(path, n)
    if _path.isdir(p) and not _path.islink(p):
      remove_dir_tree(p)
    else:
      _os.remove(p)


def remove_dir_tree(path: Path) -> None:
  remove_dir_contents(path)
  _os.rmdir(path)


def move_file(path: Path, to: str, overwrite=False) -> None:
  if not overwrite and path_exists(to):
    raise Exception('destination path already exists: {}'.format(to))
  _os.replace(path, to)


def normalize_exts(exts: Iterable[str]) -> FrozenSet[str]:
  if isinstance(exts, str): raise TypeError(exts)
  for ext in exts:
    if not isinstance(ext, str): raise TypeError(ext)
    if ext and not ext.startswith('.'): raise ValueError(ext)
  return frozenset(exts)


class PathAlreadyExists(Exception): pass

def open_new(path: Path, make_parent_dirs: bool=True, **open_args) -> IO[Any]:
  if path_exists(path):
    raise PathAlreadyExists(path)
  if make_parent_dirs:
    dirs = path_dir(path)
    if dirs: make_dirs(dirs)
  return open(path, 'w', **open_args)


read_link = _os.readlink


def _walk_dirs_and_files(dir_path: str, include_hidden: bool, file_exts: AbstractSet[str], files_as_paths: bool) -> Iterator[Tuple[str, List[str]]]:
  sub_dirs = []
  files = []
  assert dir_path.endswith('/')
  names = list_dir(dir_path, hidden=include_hidden)
  for name in names:
    path = dir_path + name
    if is_dir(path):
      sub_dirs.append(path + '/')
    elif not file_exts or path_ext(name) in file_exts:
      files.append(path if files_as_paths else name)
  yield (dir_path, files)
  for sub_dir in sub_dirs:
    yield from _walk_dirs_and_files(sub_dir, include_hidden, file_exts, files_as_paths)


def walk_dirs_and_files(*dir_paths: Path, make_abs=False, include_hidden=False, file_exts: Iterable[str]=(),
  files_as_paths=False) -> Iterator[Tuple[str, List[str]]]:
  '''
  yield (dir_path, files) pairs.
  files is an array of either names (default) or paths, depending on the files_as_paths option.
  '''
  file_exts = normalize_exts(file_exts)
  for raw_path in dir_paths:
    dir_path = abs_or_norm_path(raw_path, make_abs)
    if not dir_path.endswith('/'): dir_path += '/'
    yield from _walk_dirs_and_files(dir_path, include_hidden, file_exts, files_as_paths)


def _walk_paths_rec(dir_path: str, yield_files: bool, yield_dirs: bool, include_hidden: bool, file_exts: AbstractSet[str]) -> Iterator[str]:
  'yield paths; directory paths are distinguished by trailing slash.'
  assert dir_path.endswith('/')
  if yield_dirs:
    yield dir_path
  names = list_dir(dir_path, hidden=include_hidden)
  for name in names:
    path = path_join(dir_path, name)
    if is_dir(path):
      yield from _walk_paths_rec(path + '/', yield_files, yield_dirs, include_hidden, file_exts)
    elif yield_files and (not file_exts or path_ext(name) in file_exts):
      yield path


def walk_paths(*paths: Path, make_abs=False, yield_files=True, yield_dirs=True, include_hidden=False,
  file_exts: Iterable[str]=()) -> Iterator[str]:
  '''
  generate file and/or dir paths,
  optionally filtering hidden names and/or by file extension.
  '''
  file_exts = normalize_exts(file_exts)
  for raw_path in paths:
    path = abs_or_norm_path(raw_path, make_abs)
    if is_dir(path):
      yield from _walk_paths_rec(path + '/', yield_files, yield_dirs, include_hidden, file_exts)
    elif not path_exists(path):
      raise FileNotFoundError(path)
    elif yield_files and (not file_exts or path_ext(path) in file_exts):
      yield path


def walk_files(*paths: Path, make_abs=False, include_hidden=False, file_exts: Iterable[str]=()) -> Iterator[str]:
  return walk_paths(*paths, make_abs=make_abs, yield_files=True, yield_dirs=False,
    include_hidden=include_hidden, file_exts=file_exts)


def walk_dirs(*paths: Path, make_abs=False, include_hidden=False, file_exts: Iterable[str]=()) -> Iterator[str]:
  return walk_paths(*paths, make_abs=make_abs, yield_files=False, yield_dirs=True,
    include_hidden=include_hidden, file_exts=file_exts)


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
      return (_str_for(start_path),)
    return ()
  if prefix != comps[:len(prefix)]:
    raise PathIsNotDescendantError(end_path, start_path)
  start_i = len(prefix) + (1 if include_start else 0)
  end_i = len(comps) + (1 if include_end else 0)
  return tuple(path_join(*comps[:i]) for i in range(start_i, end_i))


def walk_dirs_up(path: Path, top: Path, include_top=True) -> Iterable[str]:
  if is_path_abs(path) ^ is_path_abs(top):
    raise MixedAbsoluteAndRelativePathsError((path, top))
  if is_dir(path):
    dir_path = path
  else:
    dir_path = path_dir(path)
    if not dir_path:
      raise PathHasNoDirError(path)
  return reversed(path_descendants(top, dir_path))


default_project_signifiers: Tuple[str, ...] = (
  '.git',
  '.project-root',
  'Package.swift',
  'craft.yaml',
  'setup.py',
)

def find_project_dir(start_dir: Path='.', top: Optional[Path]=None, include_top=False,
 project_signifiers: Iterable[str]=default_project_signifiers) -> Optional[str]:
  '''
  find a project root directory, as denoted by the presence of a file/directory in `project_signifiers`.
  By default, stops before reaching the user's home directory.
  If a signifier string contains any of '?*+^$[]', then it is treated as a regular expression.
  See default_project_signifiers.
  '''
  signifier_re = _re.compile('|'.join(f'({p if any(q in p for q in "?*+^$[]") else _re.escape(p)})' for p in project_signifiers))
  start_dir = abs_path(start_dir)
  if top is None:
    top = home_dir()
    if not start_dir.startswith(top):
      top = '/'
  else:
    top = abs_path(top)
  for path in walk_dirs_up(start_dir, top=top, include_top=include_top):
    for name in list_dir(path, hidden=True):
      if signifier_re.fullmatch(name):
        return path
  return None
