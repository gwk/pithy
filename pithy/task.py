# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import shlex as _shlex
import os as _os
import time as _time

from selectors import PollSelector as _PollSelector, EVENT_READ, EVENT_WRITE
from subprocess import DEVNULL, PIPE, Popen as _Popen
from sys import stderr, stdout
from typing import cast, Any, AnyStr, BinaryIO, Dict, IO, Iterator, List, Optional, Sequence, Tuple, Union
from .alarm import AlarmManager, Timeout

Cmd = Union[str, Sequence[str]]
Env = Dict[str, str]
Input = Union[None, int, str, bytes, BinaryIO] # int primarily for DEVNULL; could also be raw file descriptor?
File = Union[int, IO]


class NonzeroCodeExpectation:
  '''
  Type for a special marker value NONZERO, which matches any nonzero process exit code.
  '''
  def __repr__(self): return 'NONZERO'

NONZERO = NonzeroCodeExpectation()


TaskCodeExpectation = Union[None, int, NonzeroCodeExpectation]


class TaskUnexpectedExit(Exception):
  'Exception indicating that a subprocess exit code did not match the code expectation.'
  def __init__(self, cmd: Cmd, exp: TaskCodeExpectation, act: int) -> None:
    super().__init__(f'process was expected to exit with code {exp}; actual code: {act}')
    self.cmd = cmd
    self.exp = exp
    self.act = act



def launch(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, out: File=None, err: File=None, files: Sequence[File]=()) \
 -> Tuple[_Popen, Optional[bytes]]:
  '''
  Launch a subprocess, returning the subprocess.Popen object and the optional input bytes.

  The underlying Subprocess shell option is not supported
  because the rules regarding splitting strings are complex.
  User code is made clearer by just specifying the complete shell command;
  lists are used as is, while strings are split by shlex.split.

  TODO: Popen supports both text and binary files; we should too.
  TODO: support bufsize parameter.
  '''

  if isinstance(cmd, str):
    cmd = _shlex.split(cmd)

  input_bytes: Optional[bytes]
  f_in: Input
  if isinstance(stdin, str):
    f_in = PIPE
    input_bytes = stdin.encode('utf-8')
  elif isinstance(stdin, bytes):
    f_in = PIPE
    input_bytes = stdin
  else:
    f_in = stdin # presume None, PIPE, file, or DEVNULL.
    input_bytes = None

  fds = [f if isinstance(f, int) else f.fileno for f in files]

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
    env=env,
    pass_fds=fds,
  )
  return proc, input_bytes


def communicate(proc: _Popen, input_bytes: bytes=None, timeout: int=0) -> Tuple[int, bytes, bytes]:
  '''
  Communicate with and wait for a task.
  '''

  # Note: Popen provides its own timeout mechanism, based on select.
  # However, the CPython implementation of communicate() has an optimized path that is only used
  # when the timeout feature is not used.
  # The tradeoff between that implementation and this alarm-based one should be examined further.
  with AlarmManager(timeout=timeout, msg='process timed out after {timeout} seconds and was killed', on_signal=proc.kill):
    out_bytes, err_bytes = proc.communicate(input_bytes) # waits for process to complete.

  return proc.returncode, b'' if out_bytes is None else out_bytes, b'' if err_bytes is None else err_bytes


def run_gen(cmd: Cmd, cwd: str=None, env: Env=None, stdin=None, timeout: int=0, exp: TaskCodeExpectation=0,
 as_lines=True, as_text=True, merge_err=False) -> Iterator[AnyStr]:
  send: Optional[int] = None
  recv: Optional[int] = None
  if stdin == PIPE:
    stdin, send = _os.pipe()
  recv, out = _os.pipe()
  def cleanup() -> None:
    nonlocal send, recv
    if send is not None: _os.close(send)
    if recv is not None: _os.close(recv)

  try:
    proc, _ = launch(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=(out if merge_err else None))
    if send: _os.close(stdin)
    if recv: _os.close(out)

    sel = _PollSelector()
    if send: sel.register(send, EVENT_WRITE)
    if recv: sel.register(recv, EVENT_READ)
    time_start = _time.time()
    send_buffer: List[bytes] = []
    recv_bytes = b''

    while recv_bytes or sel.get_map():
      time_rem: Optional[float]
      if timeout > 0:
        time_rem = timeout - (_time.time() - time_start)
        if time_rem <= 0:
          proc.kill()
          raise Timeout(f'process timed out after {timeout} seconds and was killed')
      else:
        time_rem = None

      recv_ready = None
      send_ready = None
      if send or recv:
        for key, flags in sel.select(time_rem): # type: ignore
          if key.fd is recv: recv_ready = flags
          elif key.fd is send: send_ready = flags
          else: raise Exception(f'Task: received unknown selector key: {key}')

      if recv_ready:
        b = _os.read(key.fd, 0x8000)
        if b:
          recv_bytes += b
        else:
          assert recv is not None
          sel.unregister(recv)
          _os.close(recv)
          recv = None

      yield_bytes = b''
      if as_lines:
        idx = recv_bytes.find(0x0A)
        if idx >= 0: # found newline.
          p = idx + 1 # include newline.
          yield_bytes = recv_bytes[:p]
          recv_bytes = recv_bytes[p:]
        elif recv is None: # missing final newline.
          yield_bytes = recv_bytes
          recv_bytes = b''
      else:
        yield_bytes = recv_bytes
        recv_bytes = b''

      if yield_bytes or send_ready:
        send_bytes = yield cast(AnyStr, yield_bytes.decode('utf8') if as_text else yield_bytes)
        if send_bytes is not None:
          send_buffer.append(send_bytes)

      if send_ready:
        b = b''.join(send_buffer)
        send_buffer.clear()
        assert send is not None
        try: _os.write(send, b)
        except BrokenPipeError:
          sel.unregister(send)
          _os.close(send)
          send = None

    if recv: _os.close(recv)
    if send: _os.close(send)
    time_rem = timeout - (_time.time() - time_start)
    code = proc.wait(timeout=(time_rem if timeout > 0 else None))
    if exp is None:
      pass
    elif isinstance(exp, NonzeroCodeExpectation):
      if code == 0:
        raise TaskUnexpectedExit(cmd=cmd, exp=NONZERO, act=code)
    else:
      if code != exp: # otherwise expect exact numeric code.
        raise TaskUnexpectedExit(cmd=cmd, exp=exp, act=code)
    return code # generator will raise StopIteration(code).
  except BaseException:
    proc.kill()
    cleanup()
    raise


def run(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, out: File=None, err: File=None,
 timeout: int=0, files: Sequence[File]=(), exp: TaskCodeExpectation=0) -> Tuple[int, str, str]:
  '''
  Run a command and return (exit_code, std_out, std_err).
  '''
  proc, input_bytes = launch(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=err, files=files)
  code, out_bytes, err_bytes = communicate(proc, input_bytes, timeout)

  if exp is None:
    pass
  elif isinstance(exp, NonzeroCodeExpectation):
    if code == 0:
      raise TaskUnexpectedExit(cmd, NONZERO, code)
  else:
    if code != exp: # otherwise expect exact numeric code.
      raise TaskUnexpectedExit(cmd, exp, code)

  return code, out_bytes.decode('utf8'), err_bytes.decode('utf8')


def runCOE(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None,
 timeout: int=0, files: Sequence[File]=()) -> Tuple[int, str, str]:
  'Run a command and return exit code, std out, std err.'
  return run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=PIPE, timeout=timeout, files=files, exp=None)


def runC(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, out: BinaryIO=None, err: BinaryIO=None,
 timeout: int=0, files: Sequence[File]=()) -> int:
  'Run a command and return exit code; optional out and err.'
  assert out is not PIPE
  assert err is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=err, timeout=timeout, files=files, exp=None)
  assert e == ''
  assert o == ''
  return c


def runCO(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, err: BinaryIO=None,
 timeout: int=0, files: Sequence[File]=()) -> Tuple[int, str]:
  'Run a command and return exit code, std out; optional err.'
  assert err is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=err, timeout=timeout, files=files, exp=None)
  assert e == '', repr(e)
  return c, o


def runCE(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, out: BinaryIO=None,
 timeout: int=0, files: Sequence[File]=()) -> Tuple[int, str]:
  'Run a command and return exit code, std err; optional out.'
  assert out is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=PIPE, timeout=timeout, files=files, exp=None)
  assert o == ''
  return c, e


def runOE(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None,
 timeout: int=0, files: Sequence[File]=(), exp: TaskCodeExpectation=0) -> Tuple[str, str]:
  'Run a command and return (stdout, stderr) as strings; optional code expectation `exp`.'
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=PIPE, timeout=timeout, files=files, exp=exp)
  return o, e


def runO(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, err: BinaryIO=None,
 timeout: int=0, files: Sequence[File]=(), exp: TaskCodeExpectation=0) -> str:
  'Run a command and return stdout as a string; optional err and code expectation `exp`.'
  assert err is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=err, timeout=timeout, files=files, exp=exp)
  assert e == ''
  return o


def runE(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, out: BinaryIO=None,
 timeout: int=0, files: Sequence[File]=(), exp: TaskCodeExpectation=0) -> str:
  'Run a command and return stderr as a string; optional out and code expectation `exp`.'
  assert out is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=PIPE, timeout=timeout, files=files, exp=exp)
  assert o ==  ''
  return e

