# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
from typing import *
from typing import IO

File = Union[None, int, IO]


FR, FW, BR, BW = range(4)


class DuplexPipe:

  def __init__(self) -> None:
    self._files: List[File] = list(os.pipe() + os.pipe())

  def __enter__(self): return self

  def __exit__(self, exc_type, exc_value, traceback) -> None:
    for i in range(4): self.close(i)

  def close(self, index: int) -> None:
    f = self._files[index]
    if f is None: return
    elif isinstance(f, int): os.close(f)
    else: f.close()
    self._files[index] = None

  def _fd(self, idx: int) -> int:
    f = self._files[idx]
    if isinstance(f, int): return f
    if f is None: raise Exception('DuplexPipe file has already been closed')
    raise Exception('DuplexPipe file descriptor has already been converted to a file object')

  def _file(self, idx: int, **kwargs) -> IO:
    f = self._files[idx]
    if f is None: raise Exception('DuplexPipe file has already been closed')
    if isinstance(f, int):
      f = open(f, **kwargs)
      self._files[idx] = f
    return f

  @property
  def left_fds(self) -> Tuple[int, int]:
    return (self._fd(BR), self._fd(FW))

  @property
  def right_fds(self) -> Tuple[int, int]:
    return (self._fd(FR), self._fd(BW))

  def left_files(self, **kwargs) -> Tuple[IO, IO]:
    return (self._file(BR, mode='r', **kwargs), self._file(FW, mode='w', **kwargs))

  def right_files(self, **kwargs) -> Tuple[IO, IO]:
    return (self._file(FR, mode='r', **kwargs), self._file(BW, mode='w', **kwargs))

  def close_right(self) -> None:
    for i in (FR, BW): self.close(i)
