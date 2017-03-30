# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import shlex as _shlex

from subprocess import DEVNULL, PIPE as _pipe, Popen as _Popen
from sys import stderr, stdout
from typing import cast, Any, BinaryIO, Dict, List, Optional, Tuple, Union
from .alarm import AlarmManager, Timeout


Env = Dict[str, str]
Input = Union[None, int, str, bytes, BinaryIO] # int primarily for DEVNULL; could also be raw file descriptor?
Output = Optional[str] # TODO: support binary output.


class NonzeroCodeExpectation:
  '''
  Type for a special marker value NONZERO, which matches any nonzero process exit code.
  '''
  def __repr__(self): return 'NONZERO'

NONZERO = NonzeroCodeExpectation()


TaskCodeExpectation = Union[None, int, NonzeroCodeExpectation]


class TaskUnexpectedExit(Exception):
  'Exception indicating that a subprocess exit code did not match the code expectation.'
  def __init__(self, cmd: List[str], exp: TaskCodeExpectation, act: int) -> None:
    super().__init__(f'process was expected to exit with code {exp}; actual code: {act}')
    self.cmd = cmd
    self.exp = exp
    self.act = act


def _decode(s: Optional[bytes]) -> Output:
  'Decode optional utf-8 bytes from a subprocess.'
  return s if s is None else s.decode('utf-8')


def launch(cmd: List[str], cwd: str=None, env: Env=None, stdin: Input=None, out: BinaryIO=None, err: BinaryIO=None) -> Tuple[_Popen, Optional[bytes]]:
  '''
  Launch a subprocess, returning the subprocess.Popen object and the optional input bytes.

  The underlying Subprocess shell option is not supported
  because the rules regarding splitting strings are complex.
  User code is made clearer by just specifying the complete shell command;
  lists are used as is, while strings are split by shlex.split.
  '''

  if isinstance(cmd, str):
    cmd = _shlex.split(cmd)

  input_bytes: Union[None, bytes]
  if isinstance(stdin, str):
    f_in = _pipe
    input_bytes = stdin.encode('utf-8')
  elif isinstance(stdin, bytes):
    f_in = _pipe
    input_bytes = stdin
  else:
    f_in = stdin # presume None, _pipe, file, or DEVNULL.
    input_bytes = None

  # flushing std file descriptors guarantees consistent behavior between console and iotest;
  # otherwise we see that parent output appears after child output when run under iotest only.
  stderr.flush()
  stdout.flush()

  proc = _Popen(
    cmd,
    cwd=cwd,
    stdin=f_in,
    stdout=out,
    stderr=err,
    shell=False,
    env=env
  )
  return proc, input_bytes


def communicate(proc: _Popen, input_bytes: bytes=None, timeout: int=0) -> Tuple[int, Optional[bytes], Optional[bytes]]:
  '''
  Communicate with and wait for a task.
  '''

  # Note: Popen provides its own timeout mechanism, based on select.
  # However, the CPython implementation of communicate() has an optimized path that is only used
  # when the timeout feature is not used.
  # The tradeoff between that implementation and this alarm-based one should be examined further.
  with AlarmManager(timeout=timeout, msg='process timed out after {timeout} seconds and was killed', on_signal=proc.kill):
    out_bytes, err_bytes = proc.communicate(input_bytes) # waits for process to complete.

  return proc.returncode, out_bytes, err_bytes


def run(cmd: List[str], cwd: str=None, env: Env=None, stdin: Input=None, out: BinaryIO=None, err: BinaryIO=None,
 timeout: int=0, exp: TaskCodeExpectation=0) -> Tuple[int, Output, Output]:
  '''
  Run a command and return (exit_code, std_out, std_err).
  '''
  proc, input_bytes = launch(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=err)
  code, out_bytes, err_bytes = communicate(proc, input_bytes, timeout)

  if exp is None:
    pass
  elif isinstance(exp, NonzeroCodeExpectation):
    if code == 0:
      raise TaskUnexpectedExit(cmd, NONZERO, code)
  else:
    if code != exp: # otherwise expect exact numeric code.
      raise TaskUnexpectedExit(cmd, exp, code)

  return code, _decode(out_bytes), _decode(err_bytes)



def runC(cmd: List[str], cwd: str=None, stdin: Input=None, out: BinaryIO=None, err: BinaryIO=None, env: Env=None,
 timeout: int=0) -> int:
  'Run a command and return exit code; optional out and err.'
  assert out is not _pipe
  assert err is not _pipe
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=err, timeout=timeout, exp=None)
  assert o is None
  assert e is None
  return c


def runCO(cmd: List[str], cwd: str=None, stdin: Input=None, err: BinaryIO=None, env: Env=None,
 timeout: int=0) -> Tuple[int, Output]:
  'Run a command and return exit code, std out; optional err.'
  assert err is not _pipe
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=_pipe, err=err, timeout=timeout, exp=None)
  assert e is None
  return c, o


def runCE(cmd: List[str], cwd: str=None, stdin: Input=None, out: BinaryIO=None, env: Env=None,
 timeout: int=0) -> Tuple[int, Output]:
  'Run a command and return exit code, std err; optional out.'
  assert out is not _pipe
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=_pipe, timeout=timeout, exp=None)
  assert o is None
  return c, e


def runOE(cmd: List[str], cwd: str=None, stdin: Input=None, env: Env=None,
 timeout: int=0, exp: TaskCodeExpectation=0) -> Tuple[Output, Output]:
  'Run a command and return (stdout, stderr) as strings; optional code expectation `exp`.'
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=_pipe, err=_pipe, timeout=timeout, exp=exp)
  return o, e


def runO(cmd: List[str], cwd: str=None, stdin: Input=None, err: BinaryIO=None, env: Env=None,
 timeout: int=0, exp: TaskCodeExpectation=0) -> Output:
  'Run a command and return stdout as a string; optional err and code expectation `exp`.'
  assert err is not _pipe
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=_pipe, err=err, timeout=timeout, exp=exp)
  assert e is None
  return o


def runE(cmd: List[str], cwd: str=None, stdin: Input=None, out: BinaryIO=None, env: Env=None,
 timeout: int=0, exp: TaskCodeExpectation=0) -> Output:
  'Run a command and return stderr as a string; optional out and code expectation `exp`.'
  assert out is not _pipe
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=_pipe, timeout=timeout, exp=exp)
  assert o is None
  return e

