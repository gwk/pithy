# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Iterator
from contextlib import contextmanager
from fcntl import flock, LOCK_EX, LOCK_NB, LOCK_SH
from os import close as os_close, O_CREAT, O_RDWR, open as os_open
from os.path import realpath
from threading import Lock

from pithy.logs import logI


class AdvisoryLockError(Exception):
  'Raised when an advisory lock acquisition would deadlock the current process against a lock it already holds.'


# Process-wide registry of advisory locks held via this module, used to detect intra-process self-deadlock.
# The two maps form a single logical structure and must be read and written together under `_advisory_locks_mutex`:
# every registered fd appears in both, and a partial update would let one thread observe a torn, inconsistent state.
#   `_advisory_lock_path_holders`: realpath -> {fd: exclusive}; the forward map, queried for conflict detection by path.
#   `_advisory_lock_fd_paths`: fd -> realpath; the reverse map, so `release_advisory_lock` can locate the path from an fd.
_advisory_locks_mutex = Lock()
_advisory_lock_path_holders:dict[str,dict[int,bool]] = {}
_advisory_lock_fd_paths:dict[int,str] = {}


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

  The lock is tracked in a process-wide registry keyed by the file's `realpath`. If this process already holds a lock
  on the same file via another fd, and the requested mode is incompatible with it (exclusive against any holder, or
  shared against an exclusive holder), this raises `AdvisoryLockError` immediately rather than blocking forever against
  a lock the process cannot release. The path is resolved with `realpath`, so aliased paths (symlinks, relative vs.
  absolute) are detected; hardlinks to one inode via distinct paths are not. To upgrade a held shared lock to exclusive,
  re-flock the same fd rather than acquiring a second one; this module does not provide that.
  '''
  real_path = realpath(lock_path)
  mode = 0o660 if allow_group else 0o600
  flags = LOCK_EX if exclusive else LOCK_SH
  fd = os_open(real_path, O_RDWR | O_CREAT, mode)
  try:
    # Register the intended lock before the (possibly blocking) flock, so a concurrent thread acquiring a conflicting
    # lock on the same file sees this holder and fails fast instead of both threads deadlocking in the kernel.
    with _advisory_locks_mutex:
      holders = _advisory_lock_path_holders.get(real_path)
      if holders and (exclusive or any(holders.values())):
        lock_kind = 'exclusive' if exclusive else 'shared'
        raise AdvisoryLockError(
          f'advisory_lock: process already holds a conflicting lock; cannot acquire {lock_kind} lock for path: {lock_path!r}')
      _advisory_lock_fd_paths[fd] = real_path
      _advisory_lock_path_holders.setdefault(real_path, {})[fd] = exclusive
  except BaseException:
    os_close(fd)
    raise
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
    release_advisory_lock(fd)  # Unregister and close.
    raise
  return fd


def release_advisory_lock(fd:int) -> None:
  '''
  Release the advisory lock held on `fd` (as returned by `acquire_advisory_lock`) by unregistering and closing the fd.

  Closing the fd is sufficient to release the kernel lock: an flock lock belongs to the open file description,
  and the kernel releases it when the last fd referencing that description is closed.
  This assumes the fd is the sole reference to its description;
  a forked or duped descriptor would keep the lock held until it too is closed.
  The module does not currently support sharing fds across `fork`.

  The fd is also removed from the process-wide registry so that the file is no longer treated as held for conflict
  detection. Passing an fd that was not registered (e.g. already released) closes it but is otherwise a no-op.
  '''
  with _advisory_locks_mutex:
    real_path = _advisory_lock_fd_paths.pop(fd, None)
    if real_path is not None:
      holders = _advisory_lock_path_holders.get(real_path)
      if holders is not None:
        holders.pop(fd, None)
        if not holders:
          del _advisory_lock_path_holders[real_path]
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
  intentionally in the process-wide registry and released only when the process exits (the kernel closes all fds on process
  death).

  Because the lock stays registered, a later attempt to acquire a conflicting lock on the same file raises
  `AdvisoryLockError` rather than deadlocking. See `acquire_advisory_lock` for the parameter and conflict semantics.
  '''
  # Discard the returned fd intentionally: the registry retains it, holding the lock for the process lifetime.
  acquire_advisory_lock(lock_path, exclusive=exclusive, blocking=blocking, allow_group=allow_group)


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
