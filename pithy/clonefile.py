# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sys
from ctypes import c_char_p, c_int, c_uint, CDLL, set_errno
from errno import EEXIST, ENOENT, ENOTSUP
from os import strerror
from os.path import dirname, isdir
from typing import Callable


__all__ = ['clone', 'volume_supports_clone']


if sys.platform == 'darwin':
  libSystem = CDLL('libSystem.dylib', use_errno=True)
  clonefile = libSystem.clonefile # (UnsafePointer<Int8>!, UnsafePointer<Int8>!, UInt32) -> Int32
  clonefile.argtypes = (c_char_p, c_char_p, c_uint)
  clonefile.restype = c_int
else:
  def clonefile(src:str, dst:str, flags:int) -> int:
    raise Exception(f'clonefile is not available on this platform: {sys.platform}')


CLONE_NOFOLLOW = 1 # Int32
CLONE_NOOWNERCOPY = 2 # Int32


def clone(src:str, dst:str, follow_symlinks:bool=True, preserve_owner:bool=True, fallback:Callable[..., None]|None=None) -> None:
  '''
  Clone a file using the file system's copy-on-write semantics if available (e.g. APFS); otherwise copy.
  '''
  flags = (0 if follow_symlinks else CLONE_NOFOLLOW) | (0 if preserve_owner else CLONE_NOOWNERCOPY)
  res = clonefile(src.encode(), dst.encode(), flags)
  if res == 0: return
  assert res == -1
  en = set_errno(0)
  assert en != 0, (src, dst, res, en)
  if en == ENOTSUP and fallback is not None: # cloning not supported.
    fallback(src=src, dst=dst, follow_symlinks=follow_symlinks, preserve_owner=preserve_owner)
  elif en == ENOENT: # one of the files or intervening directories does not exist.
    dst_dir = dirname(dst)
    if dst_dir and not isdir(dst_dir): raise NotADirectoryError(dst_dir)
  elif en == EEXIST:
    raise FileExistsError(dst)
  # TODO: more elaborate diagnosis.
  raise OSError(en, strerror(en), src)


def volume_supports_clone() -> bool:
  '''
  Not all volumes support clonefile().
  A volume can be tested for clonefile() support by using getattrlist(2) to get the volume capabilities attribute ATTR_VOL_CAPABILITIES, and then testing the VOL_CAP_INT_CLONE flag.
  '''
  raise NotImplementedError
