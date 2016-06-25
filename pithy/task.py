# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import shlex as _shlex

from subprocess import PIPE as _pipe, Popen as _Popen


class ProcessExpectation(Exception):
  def __init__(self, cmd, exp, act):
    super().__init__('process was expected to return code {}; actual code: {}'.format(
      exp, act))
    self.cmd = cmd
    self.exp = exp
    self.act = act

class ProcessTimeout(Exception):
  def __init__(self, cmd, timeout):
    super().__init__('process timed out after {} seconds and was killed', timeout)
    self.cmd = cmd
    self.timeout = timeout

def _decode(s):
  return s if s is None else s.decode('utf-8')


_dev_null_file = None
def dev_null():
  global _dev_null_file
  if _dev_null_file is None:
    _dev_null_file = open('/dev/null', 'r+b')
  return _dev_null_file


def run(cmd, cwd=None, stdin=None, out=None, err=None, env=None, timeout=None, exp=0):
  '''
  run a command and return (exit_code, std_out, std_err).
  cmd: str or list of str.
  cwd: str path.
  stdin: str, bytes, open binary file (including value of dev_null()).
  out, err: open binary file or _pipe special.
  env: dict of str.
  timeout: numeric or None.
  exp: expected exit code can be None (accept any value), an integer code,
    or `...` (Ellipsis) to indicate any nonzero code.

  The special ellipsis notation is used because a bool expectation is confusing;
  nonzero implies True in Python, but False in Unix.

  the underlying Subprocess shell option is not supported
  because the rules regarding splitting strings are complex.
  user code is made clearer by just specifying the complete shell command;
  lists are used as is, while strings are split by shlex.split.
  '''

  if isinstance(cmd, str):
    cmd = _shlex.split(cmd)

  if isinstance(stdin, str):
    f_in = _pipe
    input_bytes = stdin.encode('utf-8')
  elif isinstance(stdin, bytes):
    f_in = _pipe
    input_bytes = stdin
  else:
    f_in = stdin # presume None, _pipe, or file, which includes dev_null().
    input_bytes = None

  proc = _Popen(
    cmd,
    cwd=cwd,
    stdin=f_in,
    stdout=out,
    stderr=err,
    shell=False,
    env=env
  )

  # timeout alarm handler.
  timed_out = False
  if timeout is not None:
    def alarm_handler(signum, current_stack_frame):
      # since signal handlers carry reentrancy concerns, do not do any IO within the handler.
      nonlocal timed_out
      timed_out = True
      proc.kill()

    signal.signal(signal.SIGALRM, alarm_handler) # set handler.
    signal.alarm(timeout) # set alarm.

  p_out, p_err = proc.communicate(input_bytes) # waits for process to complete.

  if timeout is not None:
    signal.alarm(0) # disable alarm.
    if timed_out:
      raise ProcessTimeout(cmd, timeout)

  code = proc.returncode
  if exp is None:
    pass
  if exp is Ellipsis:
    if code == 0:
      raise ProcessExpectation(cmd, '!= 0', code)
  else:
    if code != exp: # otherwise expect exact numeric code.
      raise ProcessExpectation(cmd, exp, code)

  return code, _decode(p_out), _decode(p_err)


def runC(cmd, cwd=None, stdin=None, out=None, err=None, env=None, timeout=None):
  'run a command and return exit code; optional out and err.'
  assert out is not _pipe
  assert err is not _pipe
  c, o, e = run(cmd, cwd, stdin, out, err, env, timeout, exp=None)
  assert o is None
  assert e is None
  return c


def runCO(cmd, cwd=None, stdin=None, err=None, env=None, timeout=None):
  'run a command and return exit code, std out; optional err.'
  assert err is not _pipe
  c, o, e = run(cmd, cwd, stdin, _pipe, err, env, timeout, exp=None)
  assert e is None
  return c, o


def runCE(cmd, cwd=None, stdin=None, out=None, env=None, timeout=None):
  'run a command and return exit code, std err; optional out.'
  assert out is not _pipe
  c, o, e = run(cmd, cwd, stdin, out, _pipe, env, timeout, exp=None)
  assert o is None
  return c, e


def runOE(cmd, cwd=None, stdin=None, env=None, timeout=None, exp=0):
  'run a command and return (stdout, stderr) as strings; optional exp.'
  c, o, e = run(cmd, cwd, stdin, _pipe, _pipe, env, timeout, exp)
  return o, e


def runO(cmd, cwd=None, stdin=None, err=None, env=None, timeout=None, exp=0):
  'run a command and return stdout as a string; optional err and exp.'
  assert err is not _pipe
  c, o, e = run(cmd, cwd, stdin, _pipe, err, env, timeout, exp)
  assert e is None
  return o


def runE(cmd, cwd=None, stdin=None, out=None, env=None, timeout=None, exp=0):
  'run a command and return stderr as a string; optional out and exp.'
  assert out is not _pipe
  c, o, e = run(cmd, cwd, stdin, out, _pipe, env, timeout, exp)
  assert o is None
  return e

