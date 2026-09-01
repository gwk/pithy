# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sys
from time import monotonic

from utest import utest_run, utest_val
from utest.proctest import TestProcess


@utest_run
def _() -> None:
  'TestProcess terminates descendants, including those which ignore SIGTERM.'
  child_code = (
    'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); '
    'print("ready", flush=True); time.sleep(30)')
  parent_code = (
    f'import subprocess,time; subprocess.Popen([{sys.executable!r}, "-c", {child_code!r}]); '
    'time.sleep(30)')

  start = monotonic()
  with TestProcess([sys.executable, '-c', parent_code], merge_stderr=True, drain_join_timeout=2) as proc:
    proc.wait_for_pattern('ready')
  utest_val(True, monotonic() - start < 1)
