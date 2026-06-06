#!/usr/bin/env python3

'''
Verify that a timeout kills the entire process group, not just the direct child.
The child shell backgrounds a grandchild that sleeps well past the timeout; because launch()
starts a new session, the timeout kill (os.killpg in task._kill) must reap the grandchild too.
Run under iotest rather than utest because it spawns real subprocesses and writes a file.
'''

import os
from time import sleep

from pithy.exceptions import Timeout
from pithy.task import communicate, launch
from utest import utest, utest_exc


pid_path = 'grandchild.pid'

# Background a grandchild (sleep), record its pid, then `wait` so the child outlives the timeout.
# All three processes share the new-session process group created by launch().
_cmd, proc, input_bytes = launch(['sh', '-c', f'sleep 10 & echo $! > {pid_path}; wait'])

# Wait for the grandchild pid to be recorded.
grandchild_pid = 0
for _ in range(500): # Up to ~5s.
  try:
    text = open(pid_path).read().strip()
  except FileNotFoundError:
    text = ''
  if text:
    grandchild_pid = int(text)
    break
  sleep(0.01)
assert grandchild_pid, 'grandchild pid was not recorded'

# The timeout fires and kills the whole group.
utest_exc(Timeout('process timed out after 1 seconds and was killed'), communicate, proc, input_bytes, 1)


def grandchild_alive() -> bool:
  'Poll until the grandchild disappears; return True if it outlives the poll window.'
  for _ in range(500): # Up to ~5s, generous for the reparented zombie to be reaped.
    try:
      os.kill(grandchild_pid, 0)
    except ProcessLookupError:
      return False
    sleep(0.01)
  return True


utest(False, grandchild_alive)
