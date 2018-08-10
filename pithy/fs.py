# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os as _os
import re as _re
import shutil as _shutil
import stat as _stat
import time as _time

from itertools import zip_longest as _zip_longest
from os import DirEntry
from os.path import expanduser as _expanduser, realpath as _realpath
from typing import AbstractSet, Any, FrozenSet, IO, Iterable, Iterator, List, Optional, TextIO, Tuple, Union
from typing.re import Pattern # type: ignore

from .clonefile import clone
from .filestatus import *
from .path import *


class PathAlreadyExists(Exception): pass
class PathHasNoDirError(Exception): pass


def add_file_execute_permissions(path:PathOrFd) -> None:
  old_perms = file_permissions(path)
  new_perms = old_perms | _stat.S_IXUSR | _stat.S_IXGRP | _stat.S_IXOTH
  _os.chmod(path, new_perms)


def change_dir(path:PathOrFd) -> None: _os.chdir(path)


def clone_or_hardlink(src:str, dst:str, follow_symlinks=True, preserve_owner=True) -> None:
  clone(src=src, dst=dst, follow_symlinks=follow_symlinks, preserve_owner=preserve_owner, fallback=None) # TODO


def clone_or_symlink(src:str, dst:str, follow_symlinks=True, preserve_owner=True) -> None:
  clone(src=src, dst=dst, follow_symlinks=follow_symlinks, preserve_owner=preserve_owner, fallback=None) # TODO


def copy_eagerly(src:str, dst:str, follow_symlinks:bool=True, preserve_owner:bool=True) -> None:
  # TODO: implementation that more precisely matches semantics of APFS clonefile.
  # TODO: test on other platforms, figure out appropriate cross platform semantics. In particular, look at BTRFS and ZFS.
  _shutil.copytree(src=src, dst=dst)


def copy_path(src:str, dst:str, overwrite:bool=True, follow_symlinks:bool=True, preserve_owner:bool=True) -> None:
  if overwrite and path_exists(dst):
    remove_path(dst)
  clone(src=src, dst=dst, follow_symlinks=follow_symlinks, preserve_owner=preserve_owner, fallback=copy_eagerly)


def expand_user(path:Path) -> str: return _expanduser(str_path(path))


default_project_signifiers: Tuple[str, ...] = (
  '.git',
  '.project-root',
  'Package.swift',
  'craft.yaml',
  'setup.py',
)

def find_project_dir(start_dir:Path='.', top:Optional[Path]=None, include_top=False,
 project_signifiers:Iterable[str]=default_project_signifiers) -> Optional[str]:
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


def home_dir() -> str: return _expanduser('~')


def is_python_file(path:Path, always_read=False) -> bool:
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


def list_dir(path:PathOrFd, exts:Iterable[str]=(), hidden=False) -> List[str]:
  '''
  Return a list of the names in the directory at `path`,
  optionally filtering by extensions in `exts`, and the `hidden` flag (defaults to False, excluding names beginning with '.').
  '''
  exts = normalize_exts(exts)
  names = sorted(_os.listdir(path))
  #^ Sort is necessary for some file systems, e.g. APFS.
  if not exts and hidden: return names # no filtering necessary.
  return [n for n in names if name_has_any_ext(n, exts) and (hidden or not n.startswith('.'))]


def list_dir_paths(path:Path, exts:Iterable[str]=(), hidden=False) -> List[str]:
  return [path_join(path, name) for name in list_dir(path, exts=exts, hidden=hidden)]


def make_dir(path:Path) -> None: return _os.mkdir(path)

def make_dirs(path:Path, mode=0o777, exist_ok=True) -> None: return _os.makedirs(path, mode, exist_ok)

def make_link(orig:Path, link:Path, absolute=False, allow_nonexistent=False, make_dirs=False, perms:Optional[int]=None) -> None:
  if perms is not None: raise NotImplementedError # TODO
  if not allow_nonexistent and not path_exists(orig):
    raise FileNotFoundError(orig)
  if absolute:
    _orig = abs_path(orig)
  else:
    _orig = rel_path(orig, start=path_dir(link))
  if make_dirs:
    link_dir = path_dir(link)
    if link_dir: _os.makedirs(link_dir, exist_ok=True)
  return _os.symlink(_orig, link)


def move_file(path:Path, to:str, overwrite=False) -> None:
  if not overwrite and path_exists(to):
    raise Exception('destination path already exists: {}'.format(to))
  _os.replace(path, to)


def name_has_any_ext(name:str, exts:FrozenSet[str]) -> bool:
  '''
  Returns True if `exts` is empty or any element of `exts` is a strict suffix of `path`.
  '''
  if name == '': raise ValueError(name) # Poorly defined for the empty string.
  if not exts: return True
  for ext in exts:
    if name != ext and name.endswith(ext): return True
  return False


def normalize_exts(exts:Iterable[str]) -> FrozenSet[str]:
  if isinstance(exts, str): raise TypeError(exts)
  for ext in exts:
    if not isinstance(ext, str): raise TypeError(ext)
    if ext and not ext.startswith('.'): raise ValueError(ext)
  return frozenset(exts)


def open_new(path:Path, make_parent_dirs:bool=True, **open_args) -> IO[Any]:
  if path_exists(path):
    raise PathAlreadyExists(path)
  if make_parent_dirs:
    dirs = path_dir(path)
    if dirs: make_dirs(dirs)
  return open(path, 'w', **open_args)


def product_needs_update(product=PathOrFd, source=PathOrFd) -> bool: # type: ignore
  return file_time_mod_or_zero(product) <= file_time_mod(source)


read_link = _os.readlink


def real_path(path:Path) -> str: return _realpath(str_path(path))


def remove_dir(path:Path) -> None:
  remove_dir_contents(path, hidden=True)
  _os.rmdir(path)


def remove_dir_contents(path:Path, hidden=False) -> None:
  for n in list_dir_paths(path, hidden=hidden):
    remove_path(n)


def remove_file(path:Path) -> None: _os.remove(path)


def remove_file_if_exists(path:Path) -> None:
  if path_exists(path):
    remove_file(path)


def remove_empty_dir(path:Path) -> None: _os.rmdir(path)

def remove_empty_dirs(path:Path) -> None: _os.removedirs(path)


def remove_path(path:Path) -> None:
  if is_dir_not_link(path): remove_dir(path)
  else: remove_file(path)


def remove_path_if_exists(path:Path) -> None:
  if path_exists(path):
    remove_path(path)


def scan_dir(path:Path, exts:Iterable[str]=(), hidden=False) -> List[DirEntry]:
  exts = normalize_exts(exts)
  entries = sorted(_os.scandir(path), key=lambda e: e.name)
  if not exts and hidden: return entries
  return [e for e in entries if name_has_any_ext(e.name, exts) and (hidden or not e.name.startswith('.'))]


def set_file_time_mod(path:PathOrFd, mtime:Optional[float]) -> None:
  '''
  Update the access and modification times of the file at `path`.
  The access time is always updated to the current time;
  `mtime` defaults to the current time.
  '''
  _os.utime(path, None if mtime is None else (_time.time(), mtime))


def touch_path(path:Path, mode=0o666) -> None:
  fd = _os.open(path, flags=_os.O_CREAT|_os.O_APPEND, mode=mode)
  try: _os.utime(fd)
  finally: _os.close(fd)


def walk_dirs(*paths:Path, make_abs=False, include_hidden=False, file_exts:Iterable[str]=()) -> Iterator[str]:
  return walk_paths(*paths, make_abs=make_abs, yield_files=False, yield_dirs=True,
    include_hidden=include_hidden, file_exts=file_exts)


def walk_dirs_and_files(*dir_paths:Path, make_abs=False, include_hidden=False, file_exts:Iterable[str]=(),
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


def _walk_dirs_and_files(dir_path:str, include_hidden:bool, file_exts:FrozenSet[str], files_as_paths:bool) -> Iterator[Tuple[str, List[str]]]:
  sub_dirs = []
  files = []
  assert dir_path.endswith('/')
  for name in list_dir(dir_path, hidden=include_hidden):
    path = dir_path + name
    if is_dir(path):
      sub_dirs.append(path + '/')
    elif name_has_any_ext(name, file_exts):
      files.append(path if files_as_paths else name)
  yield (dir_path, files)
  for sub_dir in sub_dirs:
    yield from _walk_dirs_and_files(sub_dir, include_hidden, file_exts, files_as_paths)


def walk_dirs_up(path:Path, top:Path, include_top=True) -> Iterable[str]:
  if is_path_abs(path) ^ is_path_abs(top):
    raise MixedAbsoluteAndRelativePathsError((path, top))
  if is_dir(path):
    dir_path = path
  else:
    dir_path = path_dir(path)
    if not dir_path:
      raise PathHasNoDirError(path)
  return reversed(path_descendants(top, dir_path))


def walk_files(*paths:Path, make_abs=False, include_hidden=False, file_exts:Iterable[str]=()) -> Iterator[str]:
  return walk_paths(*paths, make_abs=make_abs, yield_files=True, yield_dirs=False,
    include_hidden=include_hidden, file_exts=file_exts)


def walk_paths(*paths:Path, make_abs=False, yield_files=True, yield_dirs=True, include_hidden=False,
  file_exts:Iterable[str]=(), pass_dash=True) -> Iterator[str]:
  '''
  Generate file and/or dir paths, optionally filtering hidden names and/or by file extension.
  Treats `-` as a special symbol for stdin, and returns it unaltered and unfiltered as a special case.
  This special case can be turned off with `pass_dash=False`.
  '''
  file_exts = normalize_exts(file_exts)
  for raw_path in paths:
    if pass_dash and yield_files and raw_path == '-': # Special case to indicate stdin.
      yield '-'
      continue
    path = abs_or_norm_path(raw_path, make_abs)
    if is_dir(path):
      yield from _walk_paths_rec(path + '/', yield_files, yield_dirs, include_hidden, file_exts)
    elif not path_exists(path):
      raise FileNotFoundError(path)
    elif yield_files and name_has_any_ext(path_name(path), file_exts):
      yield path


def _walk_paths_rec(dir_path:str, yield_files:bool, yield_dirs:bool, include_hidden:bool, file_exts:FrozenSet[str]) -> Iterator[str]:
  'yield paths; directory paths are distinguished by trailing slash.'
  assert dir_path.endswith('/')
  if yield_dirs:
    yield dir_path
  for name in list_dir(dir_path, hidden=include_hidden):
    path = path_join(dir_path, name)
    if is_dir(path):
      yield from _walk_paths_rec(path + '/', yield_files, yield_dirs, include_hidden, file_exts)
    elif yield_files and name_has_any_ext(name, file_exts):
      yield path
