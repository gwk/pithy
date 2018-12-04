# Copyright 2011 George King. Permission to use this file is granted in license-gloss.txt.

r'''
TODO: register a signal handler for SIGWINCH to update sizes.
'''

from sys import stderr, stdin, stdout
import struct as _struct
import fcntl as _fcntl
import termios as _tio
import copy as _copy


def window_size(f=stdout):
  '''
  TODO: replace with shutil.get_terminal_size()?
  '''
  if not f.isatty():
    return (128, 0)
  try:
    cr = _struct.unpack('hh', _fcntl.ioctl(f, _tio.TIOCGWINSZ, b'xxxx')) # arg string length indicates length of return bytes
  except:
    print('gloss.term.window_size: ioctl failed', file=stderr)
    raise
  return int(cr[1]), int(cr[0])


# Indexes for termios list (see <termios.h>).
IFLAG = 0
OFLAG = 1
CFLAG = 2
LFLAG = 3
ISPEED = 4
OSPEED = 5
CC = 6

# Terminal modes.
RAW = 'RAW'
CBREAK = 'CBREAK'
SILENT = 'SILENT'

when_vals = (_tio.TCSANOW, _tio.TCSAFLUSH, _tio.TCSADRAIN)

class change_mode():
  '''
  context manager for altering terminal modes.
  if no file descriptor is provided, it defaults to stdin.
  '''

  def __init__(self, mode:str, fd=None, when=_tio.TCSAFLUSH, min_bytes=1, delay=0) -> None:
    assert when in when_vals
    if fd is None:
      fd = stdin.fileno()
    self.fd = fd
    self.when = when
    self.original_attrs = _tio.tcgetattr(fd)
    self.attrs = attrs = _copy.deepcopy(self.original_attrs)
    if delay > 0:
      vtime = int(delay * 10)
      assert vtime > 0
    else:
      vtime = 0
    if mode is RAW:
      attrs[IFLAG] &= ~(_tio.BRKINT | _tio.ICRNL | _tio.INPCK | _tio.ISTRIP | _tio.IXON) # type: ignore
      attrs[OFLAG] &= ~(_tio.OPOST) # type: ignore
      attrs[CFLAG] &= ~(_tio.CSIZE | _tio.PARENB) # type: ignore
      attrs[CFLAG] |= _tio.CS8 # type: ignore
      attrs[LFLAG] &= ~(_tio.ECHO | _tio.ICANON | _tio.IEXTEN | _tio.ISIG) # type: ignore
      attrs[CC][_tio.VMIN] = min_bytes # type: ignore
      attrs[CC][_tio.VTIME] = vtime # type: ignore
    elif mode is CBREAK:
      attrs[LFLAG] &= ~(_tio.ECHO | _tio.ICANON) # type: ignore
      attrs[CC][_tio.VMIN] = min_bytes # type: ignore
      attrs[CC][_tio.VTIME] = vtime # type: ignore
    elif mode is SILENT:
      attrs[LFLAG] &= ~(_tio.ECHO) # type: ignore
    else:
      raise ValueError('unkown mode for term.set_mode: {}'.format(mode))

  def __enter__(self):
    _tio.tcsetattr(self.fd, self.when, self.attrs)

  def __exit__(self, exc_type, exc_val, exc_tb):
    _tio.tcsetattr(self.fd, self.when, self.original_attrs)

