# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
import re
from collections.abc import Sequence
from pty import openpty
from re import Pattern
from signal import SIGTERM
from subprocess import Popen, TimeoutExpired
from threading import Condition, Thread
from time import monotonic
from tty import setraw
from types import TracebackType
from typing import Any, Self

from pithy.selector_gen import read_fds


class TestProcess:
  '''
  A context manager that launches a background process and captures its output.
  This is intended to run server-like processes in tests.

  A background drainer thread continuously reads from stdout (and optionally stderr)
  into in-memory buffers, eliminating any risk of pipe/pty buffer deadlocks.
  `flush_out_err()` returns and clears accumulated (stdout, stderr) as strings at any point.
  `flush_merged()` returns and clears accumulated stdout+stderr as a string; requires merge_stderr=True.
  The `_bytes` variants (`flush_out_err_bytes()`, `flush_merged_bytes()`) return raw bytes instead.

  ## Options

  By default, stdout and stderr are captured via plain pipes and merged together.
  - use_pty: Use a PTY instead of a pipe for stdout, so the child process sees a TTY
    and defaults to line-buffered output.
  - separate_stderr: Use a separate pipe for stderr so that stdout and stderr
    can be flushed independently.

  ## Lifetime management

  ### Process lifetime

  On __init__, the child process is spawned via subprocess.Popen.
  On __exit__, the process is terminated with SIGTERM and given a grace period to shut down.
  If it does not exit within that period, it is killed with SIGKILL.
  __exit__ always calls proc.wait() so no zombie is left behind.
  This applies regardless of whether __exit__ was reached normally or via an exception.

  ### Drainer thread lifetime

  The drainer thread is a daemon thread that uses read_fds() to monitor all read fds.
  It exits naturally when all fds reach EOF or raise EIO (normal PTY behavior on child exit).

  The shutdown sequence is:
  1. __exit__ terminates/kills the child process and calls proc.wait().
  2. proc.wait() guarantees the child has exited and closed its fds.
  3. The drainer sees EOF (pipes) or EIO (PTY) on all fds, causing read_fds() to terminate.
  4. __exit__ calls thread.join() with a timeout to confirm cleanup.
  5. Finally, __exit__ closes the parent-side read fds.

  The read fds are closed after the thread join, not before,
  because closing an fd while the thread is blocked on it would raise OSError on some platforms,
  whereas child exit reliably produces EOF/EIO which the drainer handles gracefully.

  If something goes catastrophically wrong and the thread does not join within the timeout,
  it is a daemon thread and will not prevent interpreter shutdown.

  ## wait_for_pattern

  `wait_for_pattern()` blocks until a regex pattern is found in the accumulated output,
  then returns the match object. This is useful for waiting on servers to start listening, e.g.:
  ```
  proc = TestProcess(['python', '-m', 'http.server', '0'], merge_stderr=True)
  with proc:
    m = proc.wait_for_pattern(r'port (\\d+)')
    port = int(m.group(1))
    # ... run tests against port ...
  ```

  The method searches the combined stdout+stderr buffer (decoded as UTF-8).
  It does not consume the buffer; call flush_out_err() or flush_merged() afterwards if desired.

  # Usage
  ```
  with TestProcess(['python', '-m', 'http.server', '8000'], merge_stderr=True) as ctx:
    # ... run tests ...
    stdout, _stderr = ctx.flush_out_err()
    if test_failed:
      print(stdout)
  ```
  '''


  def __init__(self, cmd:Sequence[str], *, merge_stderr:bool, use_pty:bool=False, term_timeout:float=5,
   drain_join_timeout:float=5, **popen_kwargs:Any) -> None:
    '''
    Args:
      cmd: Command and arguments, as for subprocess.Popen.
      use_pty: Use a PTY for stdout so the child sees a TTY.
      merge_stderr: If False, stderr is given a separate pipe and can be flushed independently.
        If True, stderr uses the same pipe as stdout.
      term_timeout: Seconds to wait after SIGTERM before sending SIGKILL.
      drain_join_timeout: Seconds to wait for drainer thread to join.
      **popen_kwargs: Additional keyword arguments passed to Popen.
        stdout, stderr, and close_fds are overridden and cannot be set.
    '''
    self.cmd = cmd
    self.merge_stderr = merge_stderr
    self.use_pty = use_pty
    self.term_timeout = term_timeout
    self.drain_join_timeout = drain_join_timeout

    self._cond = Condition()
    self._stdout_buf = bytearray()
    self._stderr_buf = bytearray()
    self._drainer_done = False

    fds_to_close_on_error:list[int] = []

    try:
      if use_pty:
        primary, replica = openpty()
        fds_to_close_on_error.extend([primary, replica])
        setraw(primary)
        stdout_read_fd = primary
        stdout_child_fd = replica
      else:
        stdout_r, stdout_w = os.pipe()
        fds_to_close_on_error.extend([stdout_r, stdout_w])
        stdout_read_fd = stdout_r
        stdout_child_fd = stdout_w

      if merge_stderr:
        stderr_read_fd = None
        stderr_child_fd = stdout_child_fd
      else:
        stderr_r, stderr_w = os.pipe()
        fds_to_close_on_error.extend([stderr_r, stderr_w])
        stderr_read_fd = stderr_r
        stderr_child_fd = stderr_w

      self._proc = Popen(cmd, stdout=stdout_child_fd, stderr=stderr_child_fd, close_fds=True, **popen_kwargs)
    except Exception:
      for fd in fds_to_close_on_error:
        os.close(fd)
      raise

    # Parent does not need the child-side fds; close them now.
    # This ensures that once the child exits, the read fds see EOF/EIO
    # rather than staying open because the parent still holds a reference.
    os.close(stdout_child_fd)
    if not merge_stderr:
      os.close(stderr_child_fd)

    self._read_fds = [stdout_read_fd]
    if stderr_read_fd is not None:
      self._read_fds.append(stderr_read_fd)

    self._drainer = Thread(target=self._drain_loop, daemon=True)
    self._drainer.start()


  def __enter__(self) -> Self:
    return self


  def __exit__(self, exc_type:type[BaseException]|None, exc_val:BaseException|None, exc_tb:TracebackType|None) -> None:
    try:
      self._shutdown_process()
    finally:
      # Join the drainer thread. The process is dead and child fds are closed, so drainer will see EOF/EIO and exit promptly.
      self._drainer.join(timeout=self.drain_join_timeout)

      # Close the read fds last, after the drainer has stopped reading.
      for fd in self._read_fds:
        os.close(fd)
      self._read_fds = []


  def wait_for_pattern(self, pattern:str|Pattern[str], timeout:float=30) -> re.Match[str]:
    '''
    Block until pattern is found in the accumulated stdout, then return the match object.
    Searches the decoded as UTF-8 (with replacement for errors).
    Does not consume the buffer; call flush_out_err() or flush_merged() afterwards if desired.
    Raises TimeoutError if the pattern is not found within the timeout, or if the process exits first.
    '''
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
    deadline = monotonic() + timeout
    with self._cond:
      while True:
        text = bytes(self._stdout_buf).decode(errors='replace')
        if m := compiled.search(text): return m
        # Check for early process exit after drainer has finished.
        if self._drainer_done:
          retcode = self._proc.poll()
          status = f'Process {self.cmd!r} exited with code {retcode}' if retcode is not None else 'still running'
          raise TimeoutError(
            f'Process {self.cmd!r} did not match pattern {compiled.pattern!r}:'
            f' {status}.\n  output:\n{self._stdout_buf!r}')
        remaining = deadline - monotonic()
        if remaining <= 0:
          raise TimeoutError(
            f'Process {self.cmd!r} timed out after {timeout}s waiting for pattern {compiled.pattern!r}.\n'
            f'  output:\n{text!r}')
        self._cond.wait(timeout=min(remaining, 0.1))


  def flush_out_err_bytes(self) -> tuple[bytes,bytes]:
    '''
    Return and clear all captured (stdout, stderr) bytes since the last flush.
    When merge_stderr is True, stderr is always empty because it is merged into stdout.
    Also checks that the child process is still running.
    Raises ChildProcessError if the process has exited unexpectedly, with the buffered output included in the exception message.
    '''
    retcode = self._proc.poll()
    if retcode is not None:
      # Process died. Join the drainer to ensure all output is captured, then take.
      self._drainer.join(timeout=self.drain_join_timeout)
      stdout_data, stderr_data = self._take_buffers()
      msg = f'Process {self.cmd!r} exited with code {retcode}.\n  stdout: {stdout_data!r}'
      if stderr_data:
        msg += f'\n  stderr: {stderr_data!r}'
      raise ChildProcessError(msg)

    return self._take_buffers()


  def flush_merged_bytes(self) -> bytes:
    '''
    Return and clear all captured stdout+stderr bytes since the last flush.
    Requires merge_stderr=True, otherwise raises ValueError.
    Also checks that the child process is still running.
    Raises ChildProcessError if the process has exited unexpectedly, with the buffered output included in the exception message.
    '''
    if not self.merge_stderr:
      raise ValueError('flush_merged_bytes() requires merge_stderr=True')

    out, err = self.flush_out_err_bytes()
    assert not err, 'flush_merged_bytes() should not return any stderr data when merge_stderr=True'
    return out


  def flush_out_err(self) -> tuple[str,str]:
    '''
    Return and clear all captured (stdout, stderr) as UTF-8 strings since the last flush.
    Invalid bytes are replaced with the Unicode replacement character.
    When merge_stderr is True, stderr is always empty because it is merged into stdout.
    Also checks that the child process is still running.
    Raises ChildProcessError if the process has exited unexpectedly, with the buffered output included in the exception message.
    '''
    out, err = self.flush_out_err_bytes()
    return out.decode(errors='replace'), err.decode(errors='replace')


  def flush_merged(self) -> str:
    '''
    Return and clear all captured stdout+stderr as a UTF-8 string since the last flush.
    Invalid bytes are replaced with the Unicode replacement character.
    Requires merge_stderr=True, otherwise raises ValueError.
    Also checks that the child process is still running.
    Raises ChildProcessError if the process has exited unexpectedly, with the buffered output included in the exception message.
    '''
    return self.flush_merged_bytes().decode(errors='replace')


  @property
  def pid(self) -> int:
    '''PID of the child process.'''
    return self._proc.pid


  @property
  def returncode(self) -> int|None:
    '''Return code of the child process, or None if still running.'''
    return self._proc.returncode


  def _take_buffers(self) -> tuple[bytes,bytes]:
    with self._cond:
      stdout_data = bytes(self._stdout_buf)
      stderr_data = bytes(self._stderr_buf)
      self._stdout_buf.clear()
      self._stderr_buf.clear()
    return stdout_data, stderr_data


  def _drain_loop(self) -> None:
    for idx, chunk in read_fds(self._read_fds):
      if chunk:
        with self._cond:
          if idx == 0:
            self._stdout_buf.extend(chunk)
          else:
            self._stderr_buf.extend(chunk)
          self._cond.notify_all()
    with self._cond:
      self._drainer_done = True
      self._cond.notify_all()


  def _shutdown_process(self) -> None:
    if self._proc.poll() is not None: return

    self._proc.send_signal(SIGTERM)
    try:
      self._proc.wait(timeout=self.term_timeout)
    except TimeoutExpired:
      self._proc.kill()
      self._proc.wait()
