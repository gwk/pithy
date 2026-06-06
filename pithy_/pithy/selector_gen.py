# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
from collections.abc import Generator, Sequence
from selectors import DefaultSelector, EVENT_READ


class SelectorTimeout(Exception):
  'Exception indicating that `read_fds` timed out with no file descriptors ready.'


def read_fds(fds:Sequence[int], timeout:float|None=None) -> Generator[tuple[int,bytes], None, None]:
  '''
  Yield (index, chunk) pairs from multiple readable file descriptors using a selector.

  Each fd in `fds` is monitored for readability. When data is available, yields (idx, chunk)
  where idx is the position of the fd in the input sequence. On EOF or EIO (normal PTY behavior
  when the child process exits), yields a final (idx, b'') sentinel for that fd and stops
  monitoring it. The generator terminates when all fds have reached EOF.

  If `timeout` is None, the selector will block indefinitely until at least one fd is ready.
  If `timeout` is not None, it is passed to selector.select() as the timeout in seconds.
  When the timeout expires with no fds ready, a SelectorTimeout exception is raised.
  '''
  sel = DefaultSelector()
  try:
    for idx, fd in enumerate(fds):
      sel.register(fd, EVENT_READ, idx)
    while sel.get_map():
      ready = sel.select(timeout)
      if not ready: raise SelectorTimeout(f'read_fds timed out after {timeout} seconds with no fds ready')
      for key, _events in ready:
        try:
          chunk = os.read(key.fd, 0x10000)
        except OSError: # EIO is the normal PTY signal that the child has exited.
          chunk = b''
        if not chunk:
          sel.unregister(key.fd)
        yield (key.data, chunk)
  finally:
    sel.close()
