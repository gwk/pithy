# Copyright 2011 George King. Permission to use this file is granted in license-gloss.txt.

'''
TODO: register a signal handler for SIGWINCH to update sizes.
'''

from copy import deepcopy
from fcntl import ioctl
from struct import unpack as struct_unpack
from sys import stderr, stdin, stdout
from termios import (BRKINT, CS8, CSIZE, ECHO, ICANON, ICRNL, IEXTEN, INPCK, ISIG, ISTRIP, IXON, OPOST, PARENB, tcgetattr,
  TCSADRAIN, TCSAFLUSH, TCSANOW, tcsetattr, TIOCGWINSZ, VMIN, VTIME)
from typing import Any, cast, Self

from .typing_utils import OptBaseExc, OptTraceback, OptTypeBaseExc


def window_size(f:Any=stdout) -> tuple[int,int]:
  '''
  Return the terminal window size attached to `f` as `(width, height)` in character cells.
  If `f` is not a tty, return (128, 0).
  TODO: replace with shutil.get_terminal_size()?
  '''
  if not f.isatty():
    return (128, 0)
  try:
    cr = struct_unpack('hh', ioctl(f, TIOCGWINSZ, b'xxxx')) # arg string length indicates length of return bytes
  except OSError:
    print('pithy.term.window_size: ioctl failed', file=stderr)
    raise
  return int(cr[1]), int(cr[0])


# Indexes for termios list (see <termios.h>, cpython/Lib/tty.py).
IFLAG = 0
OFLAG = 1
CFLAG = 2
LFLAG = 3
ISPEED = 4
OSPEED = 5
CC = 6


when_vals = (TCSANOW, TCSAFLUSH, TCSADRAIN)


class TermMode:
  '''
  A context manager for altering terminal modes.
  If no file descriptor is provided, it defaults to stdin, because these modes govern input.
  The terminal attributes are read and altered on `__enter__` and restored on `__exit__`,
  so an instance may be entered more than once.
  * delay is specified in seconds, and converted to `vtime` in deciseconds (1-255).
  '''

  def __init__(self, fd:int|None=None, when:int=TCSAFLUSH, min_bytes:int=1, delay:float=0):
    if when not in when_vals: raise ValueError(f'invalid `when`; received: {when!r}')
    if fd is None:
      fd = cast(int, stdin.fileno())
    self.fd:int = fd
    self.when = when
    self.min_bytes = min_bytes
    self.vtime = 0
    if delay > 0:
      vtime = round(delay * 10)
      if vtime < 1: raise ValueError(f'delay must be 0 or >= 0.1; received: {delay}.')
      if vtime > 255: raise ValueError(f'delay must be <= 25.5; received: {delay}.')
      self.vtime = vtime
    self.original_attrs:list[Any] = []
    self.attrs:list[Any] = []

  def __enter__(self) -> Self:
    self.original_attrs = tcgetattr(self.fd)
    self.attrs = deepcopy(self.original_attrs)
    self.alter_attrs()
    tcsetattr(self.fd, self.when, self.attrs)
    return self

  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> None:
    tcsetattr(self.fd, self.when, self.original_attrs)

  def alter_attrs(self) -> None:
    raise NotImplementedError('TermMode must be subclassed.')


class CBreakMode(TermMode):

  def alter_attrs(self) -> None:
    attrs = self.attrs
    # See cpython/Lib/tty.py for reference.
    attrs[LFLAG] &= ~(ECHO | ICANON)
    attrs[CC][VMIN] = self.min_bytes
    attrs[CC][VTIME] = self.vtime


class RawMode(TermMode):

  def alter_attrs(self) -> None:
    attrs = self.attrs
    # See cpython/Lib/tty.py for reference.
    attrs[IFLAG] &= ~(BRKINT | ICRNL | INPCK | ISTRIP | IXON)
    attrs[OFLAG] &= ~(OPOST)
    attrs[CFLAG] &= ~(CSIZE | PARENB)
    attrs[CFLAG] |= CS8
    attrs[LFLAG] &= ~(ECHO | ICANON | IEXTEN | ISIG)
    attrs[CC][VMIN] = self.min_bytes
    attrs[CC][VTIME] = self.vtime


class SilentMode(TermMode):

  def alter_attrs(self) -> None:
    attrs = self.attrs
    attrs[LFLAG] &= ~(ECHO)
