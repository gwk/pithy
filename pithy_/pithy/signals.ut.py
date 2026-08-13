# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
from signal import getsignal, SIGCHLD, SIGKILL, SIGTERM
from subprocess import CompletedProcess, run
from sys import executable

from pithy.signals import HoldSignals
from utest import utest_exc, utest_val


# Construction rejects signal sets that the design cannot honor.
utest_exc(ValueError, HoldSignals, [])
utest_exc(ValueError, HoldSignals, [SIGTERM, SIGTERM]) # Each signal's previous handler is saved just once.
utest_exc(ValueError, HoldSignals, [SIGKILL]) # Uncatchable; without this check the OS reports a bare EINVAL.
utest_exc(ValueError, HoldSignals, [SIGCHLD]) # Ignored by default, so delivering it would achieve nothing.


# A signal received inside the block is held rather than interrupting the body.
# The hold must be discarded before the block exits, because otherwise the signal is delivered and kills this test process.
previous_handler = getsignal(SIGTERM)

with HoldSignals() as hold_signals:
  utest_val(False, hold_signals.is_signal_on_hold(), 'no signal yet')
  os.kill(os.getpid(), SIGTERM)
  utest_val(True, hold_signals.is_signal_on_hold(), 'the signal is held')
  utest_val(SIGTERM, hold_signals.held, 'the held signal')
  utest_exc(ValueError, hold_signals.__enter__) # An active instance cannot be reentered.
  utest_val(SIGTERM, hold_signals.discard_held_signal(), 'discarding returns the held signal')
  utest_val(False, hold_signals.is_signal_on_hold(), 'the hold is released')

utest_val(previous_handler, getsignal(SIGTERM), 'the previous handler is restored on exit')


# Entering resets the hold, so that a leftover from a previous use does not stop the new body immediately.
reused = HoldSignals()
reused.held = SIGTERM
with reused:
  utest_val(False, reused.is_signal_on_hold(), 'entering resets the hold')


# The remaining behaviors terminate the process, so they are tested in children.

CHILD_PREAMBLE = '''
import os, sys
from signal import SIGHUP, SIGINT, signal as register_signal_handler, SIGTERM
from pithy.signals import HoldSignals

def kill_self(sig):
  os.kill(os.getpid(), sig)
  for _ in range(200000): pass # Let the pending Python-level handler run.
'''


def run_child(body:str) -> CompletedProcess[str]:
  'Run `body` as a child process, with `HoldSignals` and `kill_self` already defined.'
  return run([executable, '-c', CHILD_PREAMBLE + body], capture_output=True, text=True)


# A body that never polls still stops; the held signal is delivered when the block exits.
# This is the case that makes polling an optimization rather than the mechanism of correctness.
child = run_child('''
with HoldSignals() as h:
  kill_self(SIGTERM)
print('UNREACHABLE', file=sys.stderr)
''')
utest_val(-SIGTERM, child.returncode, 'an undischarged hold is delivered when the block exits')
utest_val('', child.stderr, 'the code after the block does not run')


# Discarding the hold is the only way to swallow the signal, and it has to be written down.
child = run_child('''
with HoldSignals() as h:
  kill_self(SIGTERM)
  h.discard_held_signal()
print('after the block', file=sys.stderr)
''')
utest_val(0, child.returncode, 'a discarded hold is not delivered')
utest_val('after the block\n', child.stderr, 'execution continues past the block')


# A second signal ends the hold at once, without waiting for the body to reach a stop point.
child = run_child('''
with HoldSignals() as h:
  kill_self(SIGTERM)
  kill_self(SIGTERM)
  print('UNREACHABLE', file=sys.stderr)
''')
utest_val(-SIGTERM, child.returncode, 'a second SIGTERM ends the hold and terminates')
utest_val('', child.stderr, 'the body does not resume')


# The held signal is delivered before the one that ended the hold,
# so a later, weaker signal cannot cancel an earlier stop request.
child = run_child('''
register_signal_handler(SIGHUP, lambda sig, frame: print('reloaded', file=sys.stderr))
with HoldSignals([SIGHUP, SIGTERM]) as h:
  kill_self(SIGTERM) # Held.
  kill_self(SIGHUP)  # Ends the hold; the pending SIGTERM must still win.
  print('UNREACHABLE', file=sys.stderr)
''')
utest_val(-SIGTERM, child.returncode, 'a weaker second signal does not cancel the held stop request')
utest_val('', child.stderr, 'a fatal first delivery preempts the second signal')


# When neither delivery is fatal, both signals reach the application, as if the manager were not there.
child = run_child('''
register_signal_handler(SIGHUP, lambda sig, frame: print('reloaded', file=sys.stderr))
with HoldSignals([SIGHUP]) as h:
  kill_self(SIGHUP)
  kill_self(SIGHUP)
  print('body resumed', file=sys.stderr)
''')
utest_val(0, child.returncode, 'non-fatal deliveries leave the process running')
utest_val('reloaded\nreloaded\nbody resumed\n', child.stderr, 'both signals are delivered, held one first')


# Ending the hold restores the previous disposition rather than SIG_DFL,
# so a second interactive Ctrl-C unwinds cleanly instead of killing the process mid-write.
child = run_child('''
try:
  with HoldSignals([SIGINT]) as h:
    kill_self(SIGINT)
    kill_self(SIGINT)
    print('UNREACHABLE', file=sys.stderr)
except KeyboardInterrupt:
  print('KeyboardInterrupt', file=sys.stderr)
finally:
  print('cleanup ran', file=sys.stderr)
''')
utest_val(0, child.returncode, 'a second SIGINT unwinds instead of terminating')
utest_val('KeyboardInterrupt\ncleanup ran\n', child.stderr, 'cleanup runs')


# An exception in flight does not suppress delivery, and delivery does not discard the exception.
child = run_child('''
with HoldSignals() as h:
  kill_self(SIGTERM)
  raise ValueError('the original failure')
''')
utest_val(-SIGTERM, child.returncode, 'the held signal is delivered even while an exception propagates')
utest_val(True, 'ValueError: the original failure' in child.stderr, 'the exception is printed before the process dies')


# When the restored handler is a Python handler, the exception it raises chains to the one in flight,
# so both appear without any explicit printing.
child = run_child('''
with HoldSignals([SIGINT]) as h:
  kill_self(SIGINT)
  raise ValueError('the original failure')
''')
utest_val(True, 'ValueError: the original failure' in child.stderr, 'the original exception is reported')
utest_val(True, 'KeyboardInterrupt' in child.stderr, 'the delivered signal is reported')
utest_val(1, child.stderr.count('ValueError: the original failure'), 'the exception is reported exactly once')
