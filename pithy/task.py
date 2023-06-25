# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os as _os
from os import access as _access, execvp, getpid as _getpid, R_OK, supports_effective_ids as _supports_effective_ids, X_OK
from os.path import dirname as _dir_name, exists as _path_exists, isfile as _is_file, join as _path_join
from selectors import EVENT_READ, EVENT_WRITE, PollSelector as _PollSelector
from shlex import quote as sh_quote, split as sh_split
from subprocess import DEVNULL, PIPE, Popen as _Popen
from sys import stderr, stdout
from time import time as _now
from typing import AnyStr, BinaryIO, cast, IO, Iterator, NoReturn, Optional, Sequence, Union

from .alarm import Alarm, Timeout


Cmd = Union[str, Sequence[str]]
Env = dict[str, str]
Input = Union[None, int, str, bytes, BinaryIO] # int primarily for DEVNULL; could also be raw file descriptor?
File = Union[int, IO]
ExitOpt = Union[bool, int, str]


class NonzeroCodeExpectation:
  'Type for a special marker value NONZERO, which matches any nonzero process exit code.'
  def __repr__(self): return 'NONZERO'

NONZERO = NonzeroCodeExpectation()


TaskCodeExpectation = Union[None, int, NonzeroCodeExpectation]


def exec(cmd:Cmd) -> NoReturn:
  cmd = tuple(sh_split(cmd) if isinstance(cmd, str) else cmd)
  execvp(cmd[0], cmd)


def launch(cmd:Cmd, cwd:str|None=None, env:Env|None=None, stdin:Input|None=None, out:File|None=None, err:File|None=None, files:Sequence[File]=(),
 note_cmd=False, lldb=False) -> tuple[tuple[str, ...], _Popen, Optional[bytes]]:
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

  fds = [f if isinstance(f, int) else f.fileno() for f in files]

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
      preexec_fn=(preexec_launch_lldb if lldb else None))

    return cmd, proc, input_bytes

  # _Popen may raise FileNotFoundError, PermissionError, or OSError.
  # The distinction is more confusing than helpful; therefore we handle them all as OSError.
  except OSError as e:
    cmd_path_as_invoked = cmd[0] # The path as seen by the command.
    path = cmd_path_as_invoked if cwd is None else _path_join(cwd, cmd_path_as_invoked) # The cmd relative to the parent cwd, or absolute.
    # TODO: If absolute, try to make path relative to parent cwd.
    if e.filename == cmd_path_as_invoked:
      _diagnose_launch_error(path, cmd_path_as_invoked, e) # Raises a more specific exception or else return.
    raise TaskLaunchUndiagnosedError(path) from e # Default.


def preexec_launch_lldb():
  '''
  Note: this relies on a race condition to work: the spawn is slow, which gives this process time to exec.
  This is not perfect; if the child process crashes very fast then LLDB might not attach in time.
  However if we try to sleep here then LLDB stops once the exec occurs, which is useless.
  GDB has something called `follow-fork-mode` that sounds like it would address this, but sticking with LLDB for now.
  '''
  pid_str = str(_getpid())
  lldb_cmd = ['PATH=/usr/bin', 'lldb', '--batch', '--one-line', 'continue', '--attach-pid', pid_str]
  lldb_str = ' '.join(lldb_cmd)
  script = f'tell application "Terminal" to do script "{lldb_str}"'
  _os.spawnvp(_os.P_WAIT, 'osascript', ['osascript', '-e', script])
  #^ Use spawn because subprocess is complex and preexec_fn is documented to be incompatible with threading.


def _diagnose_launch_error(path:str, cmd_path:str, e:OSError) -> None:
  if not _dir_name(cmd_path): # invoked as installed command.
    if _path_exists(path): raise TaskFileInvokedAsInstalledCommand(path) from e
    else: raise TaskInstalledCommandNotFound(cmd_path) from e

  if not _path_exists(path): raise TaskFileNotFound(path) from e
  if not _is_file(path): raise TaskNotAFile(path) from e
  if not _is_permitted(path, X_OK): raise TaskFileNotExecutable(path) from e

  bad_format = (e.strerror == 'Exec format error')
  if bad_format and not _is_permitted(path, R_OK): raise TaskFileNotReadable(path) from e # Read bit is necessary for scripts.

  if bad_format or isinstance(e, FileNotFoundError):
    # The 'file not found' exception might actually be due to mistyped shebang, confusingly.
    try: # Heuristic to diagnose bad shebang lines.
      with open(path, 'rb') as f:
        lead_bytes = f.read(256) # Realistically a shebang line should not be longer than this.
        line, newline, _ = lead_bytes.partition(b'\n')
        if line and (not newline or b'\0' in line): raise TaskFileBinaryIllFormed(path, line) from e # TODO: diagnose further?
        if not line.startswith(b'#!'): raise TaskFileHashbangMissing(path, line) from e
        raise TaskFileHashbangIllFormed(path, line) from e
    except (OSError, IOError):
      raise TaskLaunchError(path) from e # open or read failed; raise the original exception.


def communicate(proc: _Popen, input_bytes: bytes|None=None, timeout: int=0) -> tuple[int, bytes, bytes]:
  '''
  Communicate with and wait for a task.
  Returns (exit_code, out_bytes, err_bytes).
  '''

  # Note: Popen provides its own timeout mechanism, based on select.
  # However, the CPython implementation of communicate() has an optimized path that is only used
  # when the timeout feature is not used.
  # The tradeoff between that implementation and this alarm-based one should be examined further.
  with Alarm(timeout=timeout, msg='process timed out after {timeout} seconds and was killed', on_signal=proc.kill):
    out_bytes, err_bytes = proc.communicate(input_bytes) # waits for process to complete.

  return proc.returncode, (b'' if out_bytes is None else out_bytes), (b'' if err_bytes is None else err_bytes)


def run_gen(cmd:Cmd, cwd:str|None=None, env:Env|None=None, stdin=None, timeout:int=0, exp:TaskCodeExpectation=0,
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
    time_start = _now()
    send_buffer: list[bytes] = []
    recv_bytes = b''

    while recv_bytes or sel.get_map():
      time_rem: Optional[float]
      if timeout > 0:
        time_rem = timeout - (_now() - time_start)
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
    time_rem = timeout - (_now() - time_start)
    code = proc.wait(timeout=(time_rem if timeout > 0 else None))
    _check_exp(cmd, exp, code, exits)
    return code # generator will raise StopIteration(code).
  except BaseException:
    proc.kill()
    cleanup()
    raise


def run(cmd:Cmd, cwd:str|None=None, env:Env|None=None, stdin:Input|None=None, out:File|None=None, err:File|None=None, timeout:int=0,
 files:Sequence[File]=(), exp:TaskCodeExpectation=0,note_cmd=False, lldb=False, exits:ExitOpt=False) -> tuple[int, str, str]:
  '''
  Run a command and return (exit_code, std_out, std_err).
  '''
  cmd, proc, input_bytes = launch(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=err, files=files, note_cmd=note_cmd,
    lldb=lldb)
  code, out_bytes, err_bytes = communicate(proc, input_bytes, timeout)
  _check_exp(cmd, exp, code, exits)
  return code, out_bytes.decode('utf8'), err_bytes.decode('utf8')


def _check_exp(cmd: tuple[str, ...], exp: TaskCodeExpectation, code: int, exits:ExitOpt) -> None:
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


def runCOE(cmd:Cmd, cwd:str|None=None, env:Env|None=None, stdin:Input|None=None,
 timeout:int=0, files:Sequence[File]=(), note_cmd=False, lldb=False) -> tuple[int, str, str]:
  'Run a command and return exit code, std out, std err.'
  return run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=PIPE, timeout=timeout, files=files, exp=None,
    note_cmd=note_cmd, lldb=lldb)


def runC(cmd:Cmd, cwd:str|None=None, env:Env|None=None, stdin:Input|None=None, out:BinaryIO|None=None, err:BinaryIO|None=None,
 timeout: int=0, files: Sequence[File]=(), note_cmd=False, lldb=False) -> int:
  'Run a command and return exit code; optional out and err.'
  assert out is not PIPE
  assert err is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=err, timeout=timeout, files=files, exp=None,
    note_cmd=note_cmd, lldb=lldb)
  assert e == ''
  assert o == ''
  return c


def runCO(cmd:Cmd, cwd:str|None=None, env:Env|None=None, stdin:Input|None=None, err:BinaryIO|None=None,
 timeout: int=0, files: Sequence[File]=(), note_cmd=False, lldb=False) -> tuple[int, str]:
  'Run a command and return exit code, std out; optional err.'
  assert err is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=err, timeout=timeout, files=files, exp=None,
    note_cmd=note_cmd, lldb=lldb)
  assert e == '', repr(e)
  return c, o


def runCE(cmd: Cmd, cwd:str|None=None, env:Env|None=None, stdin:Input|None=None, out:BinaryIO|None=None,
 timeout: int=0, files: Sequence[File]=(), note_cmd=False, lldb=False) -> tuple[int, str]:
  'Run a command and return exit code, std err; optional out.'
  assert out is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=PIPE, timeout=timeout, files=files, exp=None,
    note_cmd=note_cmd, lldb=lldb)
  assert o == ''
  return c, e


def runOE(cmd: Cmd, cwd:str|None=None, env:Env|None=None, stdin:Input|None=None,
 timeout: int=0, files: Sequence[File]=(), exp: TaskCodeExpectation=0, note_cmd=False, lldb=False, exits:ExitOpt=False) \
 -> tuple[str, str]:
  'Run a command and return (stdout, stderr) as strings; optional code expectation `exp`.'
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=PIPE,
    timeout=timeout, files=files, exp=exp, note_cmd=note_cmd, lldb=lldb, exits=exits)
  return o, e


def runO(cmd: Cmd, cwd:str|None=None, env:Env|None=None, stdin:Input|None=None, err:BinaryIO|None=None,
 timeout: int=0, files: Sequence[File]=(), exp: TaskCodeExpectation=0, note_cmd=False, lldb=False, exits:ExitOpt=False) -> str:
  'Run a command and return stdout as a string; optional err and code expectation `exp`.'
  assert err is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=PIPE, err=err,
    timeout=timeout, files=files, exp=exp, note_cmd=note_cmd, lldb=lldb, exits=exits)
  assert e == ''
  return o


def runE(cmd: Cmd, cwd:str|None=None, env:Env|None=None, stdin:Input|None=None, out:BinaryIO|None=None,
 timeout: int=0, files: Sequence[File]=(), exp: TaskCodeExpectation=0, note_cmd=False, lldb=False, exits:ExitOpt=False) -> str:
  'Run a command and return stderr as a string; optional out and code expectation `exp`.'
  assert out is not PIPE
  c, o, e = run(cmd=cmd, cwd=cwd, env=env, stdin=stdin, out=out, err=PIPE,
    timeout=timeout, files=files, exp=exp, note_cmd=note_cmd, lldb=lldb, exits=exits)
  assert o ==  ''
  return e


def _is_permitted(path: str, mode: int) -> bool:
  return _access(path, mode, effective_ids=(_access in _supports_effective_ids))


class ExecutableNotFound(ValueError): pass

# Exceptions.


class UnexpectedExit(Exception):
  'Exception indicating that a subprocess exit code did not match the code expectation.'
  def __init__(self, msg: str, cmd: tuple[str, ...], exp: TaskCodeExpectation, act: int):
    super().__init__(msg)
    self.cmd = cmd
    self.exp = exp
    self.act = act


class TaskLaunchError(Exception):
  '''
  Exception indicating that `task.launch` failed.
  `launch` attempts to diagnose failures and raises a subclass of TaskLaunchError from the original.
  '''

  path: str

  @property
  def diagnosis(self) -> str:
    return 'task launch failed.'


class TaskLaunchUndiagnosedError(TaskLaunchError):
  '''
  Undiagnosed launch error.
  '''

  def __init__(self, path: str):
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str:
    return 'task launch failed (undiagnosed).'


class TaskFileBinaryIllFormed(TaskLaunchError):

  def __init__(self, path: str, first_line: bytes):
    super().__init__(path, first_line)
    self.path = path
    self.first_line = first_line

  @property
  def diagnosis(self) -> str:
    return f'file appears to be a binary; perhaps it is corrupt or the wrong format? first line: {_try_decode_repr(self.first_line)}'


class TaskFileInvokedAsInstalledCommand(TaskLaunchError):

  def __init__(self, path: str):
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return 'file exists but invocation is missing a leading `./`.'


class TaskFileHashbangMissing(TaskLaunchError):

  def __init__(self, path: str, first_line: bytes):
    super().__init__(path, first_line)
    self.path = path
    self.first_line = first_line

  @property
  def diagnosis(self) -> str:
    return f'script is missing shebang line (`#!...`); first line: {_try_decode_repr(self.first_line)}'


class TaskFileHashbangIllFormed(TaskLaunchError):

  def __init__(self, path: str, first_line: bytes):
    super().__init__(path, first_line)
    self.path = path
    self.first_line = first_line

  @property
  def diagnosis(self) -> str:
    return f'script shebang line may be ill-formed; first line: {_try_decode_repr(self.first_line)}'


class TaskFileNotExecutable(TaskLaunchError):

  def __init__(self, path: str):
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return 'file is not executable.'


class TaskFileNotFound(TaskLaunchError):

  def __init__(self, path: str):
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return 'file was not found.'


class TaskFileNotReadable(TaskLaunchError):

  def __init__(self, path: str):
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return 'file is not readable.'


class TaskInstalledCommandNotFound(TaskLaunchError):

  def __init__(self, path: str):
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return f'installed executable was not found: `{self.path}`'


class TaskNotAFile(TaskLaunchError):

  def __init__(self, path: str):
    super().__init__(path)
    self.path = path

  @property
  def diagnosis(self) -> str: return 'invocation path refers to a non-file.'


def _try_decode_repr(b: bytes) -> str:
  try: return repr(b.decode())
  except UnicodeError: return repr(b)
