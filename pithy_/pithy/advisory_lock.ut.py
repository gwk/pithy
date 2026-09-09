# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pathlib import Path
from subprocess import run
from sys import executable
from tempfile import TemporaryDirectory

from pithy.advisory_lock import advisory_lock, AdvisoryLockError
from utest import utest, utest_exc, utest_run


@utest_run
def test_contention() -> None:
  with TemporaryDirectory() as directory:
    path = str(Path(directory) / 'lock')
    with advisory_lock(path, exclusive=True):
      utest_exc(AdvisoryLockError, advisory_lock(path, exclusive=True, blocking=False).__enter__)
      result = run([executable, '-c', '''
from errno import EAGAIN, EWOULDBLOCK
from sys import argv
from pithy.advisory_lock import acquire_advisory_lock, AdvisoryLockBusy, hold_advisory_lock, advisory_lock

for acquire in (acquire_advisory_lock, hold_advisory_lock,
    lambda *args, **kwargs: advisory_lock(*args, **kwargs).__enter__()):
  for exclusive in (False, True):
    try:
      acquire(argv[1], exclusive=exclusive, blocking=False)
    except BlockingIOError as exc:
      assert isinstance(exc, AdvisoryLockBusy)
      assert type(exc.__cause__) is BlockingIOError
      assert exc.args == exc.__cause__.args
      assert exc.errno in (EAGAIN, EWOULDBLOCK)
    else:
      raise AssertionError('Expected contention.')
# Repeated acquisition attempts must not leave a stale registry entry.
''', path], capture_output=True, text=True, timeout=10)
      utest((0, '', ''), lambda: (result.returncode, result.stdout, result.stderr))
    with advisory_lock(path, exclusive=True, blocking=False): pass


@utest_run
def test_body_exception() -> None:
  with TemporaryDirectory() as directory:
    path = str(Path(directory) / 'lock')
    error = BlockingIOError('An unrelated operation failed.')

    def fail() -> None:
      with advisory_lock(path, exclusive=True, blocking=False): raise error

    utest_exc(error, fail)
    with advisory_lock(path, exclusive=True, blocking=False): pass
