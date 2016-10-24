# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os as _os
import os.path as _path
import shutil as _shutil
import stat as _stat

from itertools import zip_longest as _zip_longest


class StringIsNotAPathError(Exception): pass
class PathIsNotDescendantError(Exception): pass
class PathHasNoDirError(Exception): pass
class MixedAbsoluteAndRelativePathsError(Exception): pass

# paths.

def executable_path():
  'Return the path to this executable.'
  import __main__ # type: ignore
  return _path.realpath(__main__.__file__)

def executable_dir():
  'Return the parent directory of this excutable.'
  return _path.dirname(executable_real_path())

def is_path_abs(path):
  'Return true if the path is an absolute path.'
  return _path.isabs(path)

def normalize_path(path):
  'Normalize the path according to system convention.'
  return _path.normpath(path)

def rel_path(path, start='.'):
  'Return a path relative to start, defaulting to the current directory.'
  return _path.relpath(path, start)

def path_common_prefix(*paths):
  'Return the common path prefix for a sequence of paths.'
  try: return _path.commonpath(paths)
  except ValueError: # we want a more specific exception.
    raise MixedAbsoluteAndRelativePathsError(paths) from None

def path_dir(path):
  "Return the dir portion of a path (possibly empty), e.g. 'dir/name'."
  return _path.dirname(path)

def path_dir_or_dot(path):
  "Return the dir portion of a path, e.g. 'dir/name', or '.' in the case of no path."
  return path_dir(path) or '.'

def path_join(first, *additional):
  'Join the path with the system path separator.'
  return _path.join(first, *additional)

def path_name(path):
  "Return the name portion of a path (possibly including an extension), e.g. 'dir/name'."
  return _path.basename(path)

def path_split(path):
  np = normalize_path(path)
  if np == '/': return ['/']
  assert not np.endswith('/')
  return [comp or '/' for comp in np.split(_os.sep)]

def path_stem(path):
  'The path without the file extension; the stem may span multiple directories.'
  return split_stem_ext(path)[0]

def path_ext(path):
  'The file extension of the path.'
  return split_stem_ext(path)[1]

def path_name_stem(path):
  'The file name without extension; the name stem will not span directories.'
  return path_stem(path_name(path))

def split_dir_name(path):
  "Split the path into dir and name (possibly including an extension) components, e.g. 'dir/name'."
  return _path.split(path)

def split_dir_stem_ext(path):
  'Split the path into a (dir, stem, ext) triple.'
  dir, name = split_dir_name(path)
  stem, ext = split_stem_ext(name)
  return dir, stem, ext

def split_stem_ext(path):
  '''
  Split the path into stem (possibly spanning directories) and extension components, e.g. 'stem.ext'.
  '''
  return _path.splitext(path)

def append_path_stem_suffix(path, suffix):
  'Append suffix to the path stem.'
  stem, ext = split_stem_ext(path)
  return stem + suffix + ext

# file system.

def abs_path(path):
  'Return the absolute path corresponding to `path`.'
  return _path.abspath(path)

def abs_or_normalize_path(path, make_abs):
  'Returns the absolute path if make_abs is True, if make_abs is False, returns a normalized path.'
  return abs_path(path) if make_abs else normalize_path(path)


def path_rel_to_ancestor(path, ancestor, dot=False):
  '''
  Return the path relative to `ancestor`.
  If `path` is not descended from `ancestor`,raise PathIsNotDescendantError.
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


def path_rel_to_ancestor_or_abs(path, ancestor, dot=False):
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


def path_rel_to_current_or_abs(path, dot=False):
  return path_rel_to_ancestor_or_abs(path, current_dir(), dot=dot)


def copy_file(src, dst, follow_symlinks=True):
  'Copies file from source to destination.'
  _shutil.copy(src, dst, follow_symlinks=follow_symlinks)

def copy_dir_tree(src, dst, follow_symlinks=True, preserve_metadata=True, ignore_dangling_symlinks=False):
  'Copies a directory tree.'
  _shutil.copytree(src, dst,
    symlinks=(not follow_symlinks),
    ignore=None,
    copy_function=(_shutil.copy2 if preserve_metadata else _shutil.copy),
    ignore_dangling_symlinks=ignore_dangling_symlinks)


def expand_user(path): return _path.expanduser(path)

def home_dir(): return _path.expanduser('~')

def is_dir(path): return _path.isdir(path)

def is_file(path): return _path.isfile(path)

def is_link(path): return _path.islink(path)

def is_mount(path): return _path.ismount(path)

def link_exists(path): return _path.lexists(path)


def list_dir(path, exts=None):
  exts = normalize_exts(exts)
  names = _os.listdir(path)
  if exts is None: return names
  if isinstance(exts, str): exts = (ext,)
  return [name for name in names if path_ext(name) in exts]


def list_dir_paths(path, exts=None):
  return [path_join(path, name) for name in list_dir(path, exts=exts)]


def make_dir(path): return _os.mkdir(path)

def make_dirs(path, mode=0o777, exist_ok=True): return _os.makedirs(path, mode, exist_ok)

def path_exists(path): return _path.exists(path)

def remove_file(path): return _os.remove(path)

def remove_file_if_exists(path):
  if is_file(path):
    remove_file(path)

def remove_dir(path): return _os.rmdir(path)

def remove_dirs(path): return _os.removedirs(path)

def current_dir(): return abs_path('.')

def parent_dir(): return abs_path('..')

def change_dir(path): _os.chdir(path)

def file_time_access(path): return _os.stat(path).st_atime

def file_time_mod(path): return _os.stat(path).st_mtime

def file_time_meta_change(path): return _os.stat(path).st_ctime

def file_size(path): return _os.stat(path).st_size

def file_permissions(path): return _os.stat(path).st_mode

def is_file_not_link(path): return is_file(path) and not is_link(path)

def is_dir_not_link(path): return is_dir(path) and not is_link(path)


def is_python3_file(path, always_read=False):
  '''
  heuristics to decide if a file is a python script.
  TODO: support zip archives.
  '''
  if not always_read:
    ext = path_ext(path)
    if ext: return ext == '.py'
  try:
    with open(path, 'rb') as f:
      expected = b'#!/usr/bin/env python3\n'
      head = f.read(len(expected))
      return head == expected
  except (FileNotFoundError, IsADirectoryError): return False


def add_file_execute_permissions(path):
  old_perms = file_permissions(path)
  new_perms = old_perms | _stat.S_IXUSR | _stat.S_IXGRP | _stat.S_IXOTH
  _os.chmod(path, new_perms)

def remove_dir_contents(path):
  if _path.islink(path): raise OSError('remove_dir_contents received symlink: ' + path)
  l = _os.listdir(path)
  for n in l:
    p = path_join(path, n)
    if _path.isdir(p) and not _path.islink(p):
      remove_dir_tree(p)
    else:
      _os.remove(p)


def remove_dir_tree(path):
  remove_dir_contents(path)
  _os.rmdir(path)


def move_file(path, dest, overwrite=False):
  if path_exists(dest) and not overwrite:
    raise OSError('destination path already exists: '.format(dest))
  _os.rename(path, dest)


def normalize_exts(exts):
  if exts is None: return exts
  if isinstance(exts, str):
    exts = (exts,)
  for ext in exts:
    if not isinstance(ext, str): raise TypeError(ext)
    if ext and not ext.startswith('.'): raise ValueError(ext)
  return exts


def _walk_dirs_and_files(dir_path, include_hidden, file_exts, files_as_paths):
  sub_dirs = []
  files = []
  names = list_dir(dir_path)
  for name in names:
    if not include_hidden and name.startswith('.'):
      continue
    path = path_join(dir_path, name)
    if is_dir(path):
      sub_dirs.append(path)
    elif file_exts is None or path_ext(name) in file_exts:
      files.append(path if files_as_paths else name)
  yield (dir_path + '/', files)
  for sub_dir in sub_dirs:
    yield from _walk_dirs_and_files(sub_dir, include_hidden, file_exts, files_as_paths)


def walk_dirs_and_files(*dir_paths, make_abs=False, include_hidden=False, file_exts=None,
  files_as_paths=False):
  '''
  yield (dir_path, files) pairs.
  files is an array of either names (default) or paths, depending on the files_as_paths option.
  '''
  file_exts = normalize_exts(file_exts)
  for raw_path in dir_paths:
    dir_path = abs_or_normalize_path(raw_path, make_abs)
    yield from _walk_dirs_and_files(dir_path, include_hidden, file_exts, files_as_paths)


def _walk_paths_rec(dir_path, yield_files, yield_dirs, include_hidden, file_exts):
  'yield paths; directory paths are distinguished by trailing slash.'
  if yield_dirs:
    yield dir_path + '/'
  names = list_dir(dir_path)
  for name in names:
    if not include_hidden and name.startswith('.'):
      continue
    path = path_join(dir_path, name)
    if is_dir(path):
      yield from _walk_paths_rec(path, yield_files, yield_dirs, include_hidden, file_exts)
    elif yield_files and (file_exts is None or path_ext(name) in file_exts):
      yield path

def walk_paths(*paths, make_abs=False, yield_files=True, yield_dirs=True, include_hidden=False,
  file_exts=None):
  '''
  generate file and/or dir paths,
  optionally filtering hidden names and/or by file extension.
  '''
  file_exts = normalize_exts(file_exts)
  for raw_path in paths:
    path = abs_or_normalize_path(raw_path, make_abs)
    if is_dir(path):
      yield from _walk_paths_rec(path, yield_files, yield_dirs, include_hidden, file_exts)
    elif not path_exists(path):
      raise FileNotFoundError(path)
    elif yield_files and (file_exts is None or path_ext(path) in file_exts):
      yield path


def walk_files(*paths, make_abs=False, include_hidden=False, file_exts=None):
  return walk_paths(*paths, make_abs=make_abs, yield_files=True, yield_dirs=False,
    include_hidden=include_hidden, file_exts=file_exts)


def walk_dirs(*paths, make_abs=False, include_hidden=False, file_exts=None):
  return walk_paths(*paths, make_abs=make_abs, yield_files=False, yield_dirs=True,
    include_hidden=include_hidden, file_exts=file_exts)


def path_descendants(start_path, end_path, include_start=True, include_end=True):
  '''
  Return a tuple of paths from `start_path` to `end_path`.
  By default, `include_start` and `include_end` are both True.
  '''
  prefix = path_split(start_path)
  comps = path_split(end_path)
  if not prefix: raise StringIsNotAPath(start_path)
  if not comps: raise StringIsNotAPath(end_path)
  if prefix == comps:
    if include_start or include_end:
      return (start_path,)
    return ()
  if prefix != comps[:len(prefix)]:
    raise PathIsNotDescendantError(end_path, start_path)
  start_i = len(prefix) + (1 if include_start else 0)
  end_i = len(comps) + (1 if include_end else 0)
  return tuple(path_join(*comps[:i]) for i in range(start_i, end_i))


def walk_dirs_up(path, top, include_top=True):
  if is_path_abs(path) ^ is_path_abs(top):
    raise MixedAbsoluteAndRelativePathsError((path, top))
  if is_dir(path):
    dir_path = path
  else:
    dir_path = path_dir(path)
    if not dir_path:
      raise PathHasNoDirError(path)
  return reversed(path_descendants(top, dir_path))


default_project_signifiers = frozenset({
    '.git',
    '.project-root',
})

def find_project_dir(start_dir='.', top=None, include_top=False, project_signifiers=default_project_signifiers):
  '''
  find a project root directory, as denoted by the presence of a file/directory in `project_signifiers`,
  which defaults to:
  - .git
  - .project-root
  By default, stops before reaching the user's home directory.
  '''
  if top is None:
    top = home_dir()
  for path in walk_dirs_up(abs_path(start_dir), top=top, include_top=include_top):
    for name in list_dir(path):
      if name in project_signifiers:
        return path
  return None
