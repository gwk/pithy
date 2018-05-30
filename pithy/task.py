# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os as _os
import time as _time

from os import R_OK, X_OK, access as _access, supports_effective_ids as _supports_effective_ids
from os.path import dirname as _dir_name, exists as _path_exists, isfile as _is_file
from selectors import PollSelector as _PollSelector, EVENT_READ, EVENT_WRITE
from shlex import split as sh_split, quote as sh_quote
from subprocess import DEVNULL, PIPE, Popen as _Popen
from sys import stderr, stdout
from typing import cast, Any, AnyStr, BinaryIO, Dict, IO, Iterator, List, Optional, Sequence, Tuple, Union
from .alarm import AlarmManager, Timeout


Cmd = Union[str, Sequence[str]]
Env = Dict[str, str]
Input = Union[None, int, str, bytes, BinaryIO] # int primarily for DEVNULL; could also be raw file descriptor?
File = Union[int, IO]
ExitOpt = Union[bool, int, str]


class NonzeroCodeExpectation:
  'Type for a special marker value NONZERO, which matches any nonzero process exit code.'
  def __repr__(self): return 'NONZERO'

NONZERO = NonzeroCodeExpectation()


TaskCodeExpectation = Union[None, int, NonzeroCodeExpectation]


def launch(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, out: File=None, err: File=None, files: Sequence[File]=(),
 note_cmd=False) \
 -> Tuple[Tuple[str, ...], _Popen, Optional[bytes]]:
  '''
  Launch a subprocess, returning the normalized command as a tuple, the subprocess.Popen object and the optional input bytes.

  The underlying Subprocess shell option is not supported
  because the rules regarding splitting strings are complex.
  User code is made clearer by just specifying the complete shell command.

  If `cmd` is a list, it is used as is. If `cmd` is a string it is split by shlex.split.

  TODO: Popen supports both text and binary files; we should too.
  TODO: support bufsize parameter.
  '''

  if note_cmd: print('cmd:', fmt_cmd(cmd), file=stderr)
  if isinstance(cmd, str):
    cmd = tuple(sh_split(cmd))
  else:
    cmd = tuple(cmd)
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

  path = cast(Tuple[str, ...], cmd)[0] # For exception handling below.

  fds = [f if isinstance(f, int) else f.fileno for f in files]

  # flushing std file descriptors guarantees consistent behavior between console and iotest;
  # otherwise we see that parent output appears after child output when run under iotest only.
  stderr.flush()
  stdout.flush()

  try:
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
    return cmd, proc, input_bytes

  # _Popen may raise FileNotFoundError, PermissionError, or OSError.
  # The distinction is more confusing than helpful; therefore we handle them all as OSError.
  except OSError as e:
    _diagnose_launch_error(path, e) # Raises a more specific exception or else return.
    raise TaskLaunchError(path) from e # Default.


def _diagnose_launch_error(path: str, e: OSError) -> None:
  if e.filename != path: return # No further diagnosis.
  is_installed_cmd = not _dir_name(path)
  if is_installed_cmd:
    if _path_exists(path): raise TaskFileInvokedAsInstalledCommand(path) from e
    else: raise TaskInstalledCommandNotFound(path) from e

  if not _path_exists(path): raise TaskFileNotFound(path) from e
  if not _is_file(path): raise TaskNotAFile(path) from e
  if not _is_permitted(path, X_OK): raise TaskFileNotExecutable(path) from e

  bad_format = (e.strerror == 'Exec format error')
  if bad_format and not _is_permitted(path, R_OK): raise TaskFileNotReadable(path) from e # Read bit is necessary for scripts.

  if bad_format or isinstance(e, FileNotFoundError): # the 'file not found' might actually be due to mistyped hashbang, confusingly.
    try: # Heuristic to diagnose bad hashbang lines.
      with open(path, 'rb') as f:
        lead_bytes = f.read(256) # Realistically a hashbang line should not be longer than this.
        line, newline, _ = lead_bytes.partition(b'\n')
        if line and (not newline or b'\0' in line): raise TaskFileBinaryIllFormed(path, line) from e # TODO: diagnose further?
        if not line.startswith(b'#!'): raise TaskFileHashBangMissing(path, line) from e
        raise TaskFileHashBangIllFormed(path, line) from e
    except (OSError, IOError): pass # open or read failed; raise the original exception.


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
 as_lines=True, as_text=True, merge_err=False, exits:ExitOpt=False) -> Iterator[AnyStr]:
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
    cmd, proc, _ = launch(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=(out if merge_err else None))
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
        for key, flags in sel.select(time_rem):
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
    _check_exp(cmd, exp, code, exits)
    return code # generator will raise StopIteration(code).
  except BaseException:
    proc.kill()
    cleanup()
    raise


def run(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, out: File=None, err: File=None, timeout: int=0,
 files: Sequence[File]=(), exp: TaskCodeExpectation=0, note_cmd=False, exits:ExitOpt=False) -> Tuple[int, str, str]:
  '''
  Run a command and return (exit_code, std_out, std_err).
  '''
  cmd, proc, input_bytes = launch(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=err, files=files, note_cmd=note_cmd)
  code, out_bytes, err_bytes = communicate(proc, input_bytes, timeout)
  _check_exp(cmd, exp, code, exits)
  return code, out_bytes.decode('utf8'), err_bytes.decode('utf8')


def _check_exp(cmd: Tuple[str, ...], exp: TaskCodeExpectation, code: int, exits:ExitOpt) -> None:
  if exp is None: return
  elif isinstance(exp, NonzeroCodeExpectation):
    if code != 0: return
    exp_desc = 'expected task to fail but it exited cleanly'
  else:
    if code == exp: return
    exp_desc = 'task failed' if exp == 0 else f'expected task to exit with code {exp}, but received {code}'
  if exits != False: exit(exits if isinstance(exits, str) else f'{exp_desc}; command: `{fmt_cmd(cmd)}`')
  raise UnexpectedExit(exp_desc, cmd, exp, code)


def fmt_cmd(cmd: Sequence[str]) -> str: return ' '.join(sh_quote(word) for word in cmd)


def runCOE(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None,
 timeout: int=0, files: Sequence[File]=(), note_cmd=False) -> Tuple[int, str, str]:
  'Run a command and return exit code, std out, std err.'
  return run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=PIPE, timeout=timeout, files=files, exp=None, note_cmd=note_cmd)


def runC(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, out: BinaryIO=None, err: BinaryIO=None,
 timeout: int=0, files: Sequence[File]=(), note_cmd=False) -> int:
  'Run a command and return exit code; optional out and err.'
  assert out is not PIPE
  assert err is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=err, timeout=timeout, files=files, exp=None, note_cmd=note_cmd)
  assert e == ''
  assert o == ''
  return c


def runCO(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, err: BinaryIO=None,
 timeout: int=0, files: Sequence[File]=(), note_cmd=False) -> Tuple[int, str]:
  'Run a command and return exit code, std out; optional err.'
  assert err is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=err, timeout=timeout, files=files, exp=None, note_cmd=note_cmd)
  assert e == '', repr(e)
  return c, o


def runCE(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, out: BinaryIO=None,
 timeout: int=0, files: Sequence[File]=(), note_cmd=False) -> Tuple[int, str]:
  'Run a command and return exit code, std err; optional out.'
  assert out is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=PIPE, timeout=timeout, files=files, exp=None, note_cmd=note_cmd)
  assert o == ''
  return c, e


def runOE(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None,
 timeout: int=0, files: Sequence[File]=(), exp: TaskCodeExpectation=0, note_cmd=False, exits:ExitOpt=False) -> Tuple[str, str]:
  'Run a command and return (stdout, stderr) as strings; optional code expectation `exp`.'
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=PIPE,
    timeout=timeout, files=files, exp=exp, note_cmd=note_cmd, exits=exits)
  return o, e


def runO(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, err: BinaryIO=None,
 timeout: int=0, files: Sequence[File]=(), exp: TaskCodeExpectation=0, note_cmd=False, exits:ExitOpt=False) -> str:
  'Run a command and return stdout as a string; optional err and code expectation `exp`.'
  assert err is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=err,
    timeout=timeout, files=files, exp=exp, note_cmd=note_cmd, exits=exits)
  assert e == ''
  return o


def runE(cmd: Cmd, cwd: str=None, env: Env=None, stdin: Input=None, out: BinaryIO=None,
 timeout: int=0, files: Sequence[File]=(), exp: TaskCodeExpectation=0, note_cmd=False, exits:ExitOpt=False) -> str:
  'Run a command and return stderr as a string; optional out and code expectation `exp`.'
  assert out is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=PIPE,
    timeout=timeout, files=files, exp=exp, note_cmd=note_cmd, exits=exits)
  assert o ==  ''
  return e


def _is_permitted(path: str, mode: int) -> bool:
  return _access(path, mode, effective_ids=(_access in _supports_effective_ids))


# Exceptions.


class UnexpectedExit(Exception):
  'Exception indicating that a subprocess exit code did not match the code expectation.'
  def __init__(self, msg: str, cmd: Tuple[str, ...], exp: TaskCodeExpectation, act: int) -> None:
    super().__init__(msg)
    self.cmd = cmd
    self.exp = exp
    self.act = act


class TaskLaunchError(Exception):
  '''
  Exception indicating that `task.launch` failed
  `launch` attempts to diagnose failures and raises TaskLaunchError or subclass from the original.
  '''

  path: str

  @property
  def diagnosis(self) -> str: raise NotImplementedError


class TaskFileBinaryIllFormed(TaskLaunchError):

  def __init__(self, path: str, first_line: bytes) -> None:
    super().__init__(path, first_line)
    self.path = path
    self.first_line = first_line

  @property
  def diagnosis(self) -> str:
    return f'file appears to be a binary; perhaps it is corrupt or the wrong format? first line: {_try_decode_repr(self.first_line)}'


class TaskFileInvokedAsInstalledCommand(TaskLaunchError):

  def __init__(self, path: str) -> None:
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return 'file exists but invocation is missing a leading `./`.'


class TaskFileHashBangMissing(TaskLaunchError):

  def __init__(self, path: str, first_line: bytes) -> None:
    super().__init__(path, first_line)
    self.path = path
    self.first_line = first_line

  @property
  def diagnosis(self) -> str:
    return f'script is missing hashbang line (`#!...`); first line: {_try_decode_repr(self.first_line)}'


class TaskFileHashBangIllFormed(TaskLaunchError):

  def __init__(self, path: str, first_line: bytes) -> None:
    super().__init__(path, first_line)
    self.path = path
    self.first_line = first_line

  @property
  def diagnosis(self) -> str:
    return f'script hashbang line may be ill-formed; first line: {_try_decode_repr(self.first_line)}'


class TaskFileNotExecutable(TaskLaunchError):

  def __init__(self, path: str) -> None:
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return 'file is not executable.'


class TaskFileNotFound(TaskLaunchError):

  def __init__(self, path: str) -> None:
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return 'file was not found.'


class TaskFileNotReadable(TaskLaunchError):

  def __init__(self, path: str) -> None:
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return 'file is not readable.'


class TaskInstalledCommandNotFound(TaskLaunchError):

  def __init__(self, path: str) -> None:
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return 'installed command was not found.'


class TaskNotAFile(TaskLaunchError):

  def __init__(self, path: str) -> None:
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return 'invocation path refers to a non-file.'


def _try_decode_repr(b: bytes) -> str:
  try: return repr(b.decode())
  except UnicodeError: return repr(b)
