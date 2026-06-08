# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Iterator
from contextlib import contextmanager
from fcntl import flock, LOCK_EX, LOCK_NB, LOCK_SH, LOCK_UN
from os import close as os_close, O_CREAT, O_RDWR, open as os_open

from pithy.logs import logI


@contextmanager
def advisory_lock(lock_path:str, *, exclusive:bool, blocking:bool=True, allow_group:bool=False) -> Iterator[None]:
  '''
  Acquire a shared or exclusive advisory flock on the sentinel file at `lock_path`.

  exclusive=False (LOCK_SH):
  * Multiple holders coexist.
  * Blocks or raises if there is a prior exclusive holder.

  exclusive=True (LOCK_EX):
  * Only one holder at a time.
  * Blocks or raises if any other holder is present.

  blocking=True (default): wait indefinitely; logs a "waiting" message.
  blocking=False: raise `BlockingIOError` immediately if the lock cannot be acquired.

  allow_group=False (mode 0o600) (default):
  * Only the file owner can open and participate in the lock.
  allow_group=True (mode 0o660):
  * Group members may also open and participate in the lock.
  * Note: the mode only takes effect when the file is first created; it does not chmod an existing file.
    Thus the lock file may end up having a different owner than that of the parent directory.

  The lock is automatically released when the fd is closed, including on process death.
  Keep the lock file on a local filesystem; flock over NFS is unreliable.
  '''
  mode = 0o660 if allow_group else 0o600
  flags = LOCK_EX if exclusive else LOCK_SH
  fd = os_open(lock_path, O_RDWR | O_CREAT, mode)
  try:
    if blocking:
      try:
        flock(fd, flags | LOCK_NB)
      except BlockingIOError:
        lock_kind = 'exclusive' if exclusive else 'shared'
        logI(f'db_lock: waiting for {lock_kind} lock.', lock_path=lock_path)
        flock(fd, flags)
    else:
      flock(fd, flags | LOCK_NB)
    yield
  finally:
    flock(fd, LOCK_UN)
    os_close(fd)


def is_db_locked(lock_path:str, *, allow_group:bool=False) -> bool:
  'Return True if any process currently holds the db lock (shared or exclusive).'
  mode = 0o660 if allow_group else 0o600
  fd = os_open(lock_path, O_RDWR | O_CREAT, mode)
  try:
    flock(fd, LOCK_EX | LOCK_NB)
    flock(fd, LOCK_UN)
    return False
  except BlockingIOError:
    return True
  finally:
    os_close(fd)
