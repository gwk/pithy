# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import DirEntry, stat as _stat, stat_result as StatResult
from stat import *
from typing import Optional, NamedTuple, Union
from .path import Path, PathOrFd


class FileStatus(NamedTuple):
  '''
  Reinterpretation of standard stat_result:
  * nicer names for the dfields;
  * omits atime and atime_ns (which are not useful due to modern `noatime` semantics);
  * splits `mode` into `type` and `perms` fields.
  '''
  birth_time: int
  block_count: int
  block_size: int
  ctime: float
  ctime_ns: int
  device: int
  device_type: int
  flags: int
  generation: int
  group_id: int
  inode: int
  link_count: int
  mode: int
  mtime: float
  mtime_ns: int
  path: str
  perms: int
  size: int
  type: int
  user_id: int

  @staticmethod
  def from_stat_result(path: str, stat_result: StatResult) -> 'FileStatus':
    s = stat_result
    mode = s.st_mode
    return FileStatus(
      birth_time=s.st_birthtime,
      block_count=s.st_blocks,
      block_size=s.st_blksize,
      ctime=s.st_ctime,
      ctime_ns=s.st_ctime_ns,
      device=s.st_dev,
      device_type=s.st_rdev,
      flags=s.st_flags,
      generation=s.st_gen,
      group_id=s.st_gid,
      inode=s.st_ino,
      link_count=s.st_nlink,
      mode=mode,
      mtime=s.st_mtime,
      mtime_ns=s.st_mtime_ns,
      path=path,
      perms=S_IMODE(mode),
      size=s.st_size,
      type=S_IFMT(mode),
      user_id=s.st_uid)

  @classmethod
  def from_dir_entry(class_, entry: DirEntry, follow_symlinks=True) -> Optional['FileStatus']:
    return class_.from_stat_result(entry.path, entry.stat(follow_symlinks=follow_symlinks)) # type: ignore


  # File type tests derived from Python's stat.py.

  @property
  def is_block_device(self) -> bool: return self.type == S_IFBLK

  @property
  def is_character_device(self) -> bool: return self.type == S_IFCHR

  @property
  def is_dir(self) -> bool: return self.type == S_IFDIR

  @property
  def is_fifo(self) -> bool: return self.type == S_IFIFO

  @property
  def is_file(self) -> bool: return self.type == S_IFREG

  @property
  def is_link(self) -> bool: return self.type == S_IFLNK

  @property
  def is_socket(self) -> bool: return self.type == S_IFSOCK


  # Permissions.

  @property
  def is_suid(self) -> bool: return bool(self.perms & S_ISUID)

  @property
  def is_guid(self) -> bool: return bool(self.perms & S_ISGID)

  @property
  def is_sticky(self) -> bool: return bool(self.perms & S_ISVTX)

  @property
  def owner_perms(self) -> int: return self.perms & S_IRWXU

  @property
  def group_perms(self) -> int: return self.perms & S_IRWXG

  @property
  def other_perms(self) -> int: return self.perms & S_IRWXO

  @property
  def is_owner_readable(self) -> bool: return bool(self.perms & S_IRUSR)

  @property
  def is_owner_writeable(self) -> bool: return bool(self.perms & S_IWUSR)

  @property
  def is_owner_executable(self) -> bool: return bool(self.perms & S_IXUSR)

  @property
  def is_group_readable(self) -> bool: return bool(self.perms & S_IRGRP)

  @property
  def is_group_writeable(self) -> bool: return bool(self.perms & S_IWGRP)

  @property
  def is_group_executable(self) -> bool: return bool(self.perms & S_IXGRP)

  @property
  def is_other_readable(self) -> bool: return bool(self.perms & S_IROTH)

  @property
  def is_other_writeable(self) -> bool: return bool(self.perms & S_IWOTH)

  @property
  def is_other_executable(self) -> bool: return bool(self.perms & S_IXOTH)


  # Descriptions.

  @property
  def type_char(self) -> str: return _type_chars[self.type]

  @property
  def type_desc(self) -> str: return _type_descs[self.type]


  @property
  def perms_string(self) -> str:
    parts = [] # user, group, other.
    for part_char, part_table in _perm_chars:
        chars = part_char
        for bit, char in part_table:
          chars += char if (self.perms & bit) else '-'
        parts.append(chars)
    if self.is_suid: parts.append('suid')
    if self.is_guid: parts.append('sgid')
    if self.is_sticky: parts.append('sticky')
    return ' '.join(parts)

  @property
  def mode_str(self) -> str:
    return f'{self.type_char} {self.perms_string}'


def file_status(path_or_fd:PathOrFd, follow_symlinks:bool=True) -> Optional[FileStatus]:
  try: s = _stat(path_or_fd, follow_symlinks=follow_symlinks)
  except FileNotFoundError: return None
  path = '' if isinstance(path_or_fd, int) else str(path_or_fd)
  return FileStatus.from_stat_result(path, s)



def dir_entry_type_char(entry: DirEntry) -> str:
  '''
  Return a single uppercase letter string denoting the file type of the DirEntry.
  Because DirEntry does not expose the complete `stat` type field,
  this is limited to `D`, `F`, `L`, or `U` for other/unknown type,
  and thus is not necessarily equal to the letter obtained from `FileStatus.type_char`.
  '''
  if entry.is_symlink(): return 'L'
  if entry.is_dir(): return 'D'
  if entry.is_file(): return 'F'
  return 'U'


_type_chars = {
  S_IFBLK   : 'B',
  S_IFCHR   : 'C',
  S_IFDIR   : 'D',
  S_IFIFO   : 'P',
  S_IFLNK   : 'L',
  S_IFREG   : 'F', # traditionally '-'.
  S_IFSOCK  : 'S', # traditionally '-'.
}


_type_descs = {
  S_IFBLK   : 'block device',
  S_IFCHR   : 'character device',
  S_IFDIR   : 'directory',
  S_IFIFO   : 'named pipe',
  S_IFLNK   : 'link',
  S_IFREG   : 'file',
  S_IFSOCK  : 'socket',
}


_perm_chars = (
  ('u:', (
    (S_IRUSR, 'r'),
    (S_IWUSR, 'w'),
    (S_IXUSR, 'x'))),
  ('g:', (
    (S_IRGRP, 'r'),
    (S_IWGRP, 'w'),
    (S_IXGRP, 'x'))),
  ('o:', (
    (S_IROTH, 'r'),
    (S_IWOTH, 'w'),
    (S_IXOTH, 'x'))),
)


