# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Iterator
from contextlib import contextmanager
from fcntl import flock, LOCK_EX, LOCK_NB, LOCK_SH
from os import close as os_close, O_CREAT, O_RDWR, open as os_open
from os.path import realpath

from pithy.logs import logI


def acquire_advisory_lock(lock_path:str, *, exclusive:bool, blocking:bool=True, allow_group:bool=False) -> int:
  '''
  Open `lock_path`, acquire a shared or exclusive advisory flock, and return the open fd.

  The caller owns the returned fd and must release it with `release_advisory_lock` (or directly via `os.close`).
  This is the building block for callers whose lock lifetime is tied to an object rather than a lexical `with` block;
  prefer the `advisory_lock` context manager or `hold_advisory_lock` when they fit.

  The file's contents are irrelevant to the lock; flock locks the open file description, not the bytes.
  The file is commonly a dedicated empty sentinel, but may be any regular file, including a data file with content;
  the file is opened with O_RDWR but is neither read, written, nor truncated.
  Note: O_CREAT means the file is created if it does not exist, so this never fails on a missing path.

  exclusive=False (LOCK_SH):
  * Multiple holders coexist.
  * Blocks or raises if there is a prior exclusive holder.

  exclusive=True (LOCK_EX):
  * Only one holder at a time.
  * Blocks or raises if any other holder is present.

  blocking=True: wait indefinitely; logs a "waiting" message.
  blocking=False: raise `BlockingIOError` immediately if the lock cannot be acquired.

  allow_group=False (mode 0o600):
  * Only the file owner can open and participate in the lock.
  allow_group=True (mode 0o660):
  * Group members may also open and participate in the lock.
  * Note: the mode only takes effect when the file is first created; it does not chmod an existing file.
    Thus the lock file may end up having a different owner than that of the parent directory.

  On any failure to acquire, the fd is closed before the exception propagates.
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
        logI(f'advisory_lock: waiting for {lock_kind} lock.', lock_path=lock_path)
        flock(fd, flags)
    else:
      flock(fd, flags | LOCK_NB)
  except BaseException:
    os_close(fd)
    raise
  return fd


def release_advisory_lock(fd:int) -> None:
  '''
  Release the advisory lock held on `fd` (as returned by `acquire_advisory_lock`) by closing the fd.

  Closing the fd is sufficient: an flock lock belongs to the open file description,
  and the kernel releases it when the last fd referencing that description is closed.
  This assumes the fd is the sole reference to its description;
  a forked or duped descriptor would keep the lock held until it too is closed.
  The module does not currently support sharing fds across `fork`.
  '''
  os_close(fd)


@contextmanager
def advisory_lock(lock_path:str, *, exclusive:bool, blocking:bool=True, allow_group:bool=False) -> Iterator[None]:
  '''
  Acquire a shared or exclusive advisory flock on the file at `lock_path` for the duration of the `with` block.

  The lock is released when the block exits. See `acquire_advisory_lock` for the semantics of the parameters.
  Alternatively, use `hold_advisory_lock` to hold the lock for the lifetime of the process.
  '''
  fd = acquire_advisory_lock(lock_path, exclusive=exclusive, blocking=blocking, allow_group=allow_group)
  try:
    yield
  finally:
    release_advisory_lock(fd)


def hold_advisory_lock(lock_path:str, *, exclusive:bool, blocking:bool=True, allow_group:bool=False) -> None:
  '''
  Acquire a shared or exclusive advisory flock on the file at `lock_path` and hold it for the remaining lifetime of the process.

  Unlike the `advisory_lock` context manager, this returns with the lock held and does not relieve it; the open fd is retained
  intentionally and released only when the process exits (the kernel closes all fds on process death).

  Raises `ValueError` if this process already holds a lock acquired here for the same file;
  re-locking the same file via a second fd in one process can deadlock.
  The path is resolved with `realpath` before comparison, so aliased paths (symlinks, relative vs. absolute) are detected.
  See `acquire_advisory_lock` for the parameter semantics.
  '''
  real_path = realpath(lock_path)
  if real_path in _held_advisory_locks:
    raise ValueError(f'advisory_lock: process already holds a lifetime lock for path: {lock_path!r}')
  fd = acquire_advisory_lock(real_path, exclusive=exclusive, blocking=blocking, allow_group=allow_group)
  _held_advisory_locks[real_path] = fd


_held_advisory_locks:dict[str,int] = {}


def is_advisory_locked(lock_path:str, *, allow_group:bool=False) -> bool:
  'Return True if any process currently holds an advisory lock on `lock_path` (shared or exclusive).'
  mode = 0o660 if allow_group else 0o600
  fd = os_open(lock_path, O_RDWR | O_CREAT, mode)
  try:
    flock(fd, LOCK_EX | LOCK_NB)
    return False
  except BlockingIOError:
    return True
  finally:
    os_close(fd)
