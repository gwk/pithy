# Copyright 2011 George King. Permission to use this file is granted in license-gloss.txt.

'''
TODO: register a signal handler for SIGWINCH to update sizes.
'''

import fcntl as _fcntl
import struct as _struct
from copy import deepcopy
from sys import stderr, stdout
from termios import (BRKINT, CS8, CSIZE, ECHO, ICANON, ICRNL, IEXTEN, INPCK, ISIG, ISTRIP, IXON, OPOST, PARENB, tcgetattr,
  TCSADRAIN, TCSAFLUSH, TCSANOW, tcsetattr, TIOCGWINSZ, VMIN, VTIME)

from .typing_utils import OptBaseExc, OptTraceback, OptTypeBaseExc


def window_size(f=stdout):
  '''
  TODO: replace with shutil.get_terminal_size()?
  '''
  if not f.isatty():
    return (128, 0)
  try:
    cr = _struct.unpack('hh', _fcntl.ioctl(f, TIOCGWINSZ, b'xxxx')) # arg string length indicates length of return bytes
  except:
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
  If no file descriptor is provided, it defaults to stdout.
  '''

  def __init__(self, fd:int|None=None, when:int=TCSAFLUSH, min_bytes:int=1, delay:int=0):
    assert when in when_vals, when
    if fd is None:
      fd = stdout.fileno()
    self.fd = fd
    self.when = when
    self.min_bytes = min_bytes
    self.original_attrs = tcgetattr(fd)
    self.attrs = deepcopy(self.original_attrs)
    self.vtime = 0
    if delay > 0:
      self.vtime = int(delay * 10)
      if self.vtime <= 0: raise ValueError(f'delay must be 0 or greater than 0.1s; received: {delay}')
    self.alter_attrs()

  def __enter__(self):
    tcsetattr(self.fd, self.when, self.attrs)

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
