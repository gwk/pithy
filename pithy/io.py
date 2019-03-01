# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import close as os_close, open as os_open, read as os_read, O_RDONLY, O_NONBLOCK
from pprint import pprint
from sys import argv, stdin, stdout, stderr
from string import Template
from typing import Any, Callable, ContextManager, Iterable, Iterator, TextIO, TypeVar, Union
from .typing import OptTypeBaseExc, OptBaseExc, OptTraceback
from .desc import writeD, errD, outD


_T = TypeVar('_T')

# basic printing.

def writeZ(file: TextIO, *items: Any, sep='', end='', flush=False) -> None:
  "Write `items` to file; default sep='', end=''."
  print(*items, sep=sep, end=end, file=file, flush=flush)

def writeS(file: TextIO, *items: Any, sep='', flush=False) -> None:
  "Write `items` to file; sep='', end=' '."
  print(*items, sep=sep, end=' ', file=file, flush=flush)

def writeSZ(file: TextIO, *items: Any, flush=False) -> None:
  "Write `items` to file; sep=' ', end=''."
  print(*items, sep=' ', end='', file=file, flush=flush)

def writeSS(file: TextIO, *items: Any, flush=False) -> None:
  "Write `items` to file; sep=' ', end=''."
  print(*items, sep=' ', end=' ', file=file, flush=flush)

def writeL(file: TextIO, *items: Any, sep='', flush=False) -> None:
  "Write `items` to file; sep='', end='\\n'."
  print(*items, sep=sep, end='\n', file=file, flush=flush)

def writeN(file: TextIO, *items: Any, sep='', flush=False) -> None:
  "Write `items` to file; sep='', end=('' if items and items[-1].endswith('\\n') else '\\n')."
  end = ('' if items and items[-1].endswith('\n') else '\n')
  print(*items, sep=sep, end=end, file=file, flush=flush)

def writeSL(file: TextIO, *items: Any, flush=False) -> None:
  "Write `items` to file; sep=' ', end='\\n'."
  print(*items, sep=' ', end='\n', file=file, flush=flush)

def writeSN(file: TextIO, *items: Any, flush=False) -> None:
  "Write `items` to file; sep='', end=('' if items and items[-1].endswith('\\n') else '\\n')."
  end = ('' if items and items[-1].endswith('\n') else '\n')
  print(*items, sep=' ', end=end, file=file, flush=flush)

def writeLL(file: TextIO, *items: Any, flush=False) -> None:
  "Write `items` to file; sep='\\n', end='\\n'."
  print(*items, sep='\n', end='\n', file=file, flush=flush)

def writeLSSL(file: TextIO, *items: Any, flush=False) -> None:
  "Write `items` to file; sep='\\n  ', end='\\n'."
  print(*items, sep='\n  ', end='\n', file=file, flush=flush)


# templated format printing.

def writeTF(file: TextIO, template_fmt, *items: Any, flush=False, **keyed_items: Any) -> None:
  """
  Expand the format string with keyed_items, then format the string; end=''.
  Useful for constructing dynamic format strings.
  """
  fmt = Template(template_fmt).substitute(**keyed_items)
  print(fmt.format(*items, **keyed_items, end='', file=file, flush=flush))


def writeTFL(file: TextIO, template_fmt, *items: Any, flush=False, **keyed_items: Any) -> None:
  """
  Expand the format string template with keyed_items, then format the string; end='\\n'
  Useful for constructing dynamic format strings.
  """
  fmt = Template(template_fmt).substitute(**keyed_items)
  print(fmt.format(*items, **keyed_items, file=file, flush=flush))


def writeP(file: TextIO, *items: Any, label=None, indent=2, **opts: Any) -> None:
  'Pretty print to file.'
  if label is not None:
    file.write(label)
    file.write (': ')
  for item in items:
    pprint(item, stream=file, indent=indent, **opts)


# std out.

def outZ(*items: Any, sep='', end='', flush=False) -> None:
  "Write `items` to std out; sep='', end=''."
  print(*items, sep=sep, end=end, flush=flush)

def outS(*items: Any, sep='', flush=False) -> None:
  "Write `items` to std out; sep='', end=' '."
  print(*items, sep=sep, end=' ', flush=flush)

def outSZ(*items: Any, flush=False) -> None:
  "Write `items` to std out; sep=' ', end=''."
  print(*items, sep=' ', end='', flush=flush)

def outSS(*items: Any, flush=False) -> None:
  "Write `items` to std out; sep=' ', end=' '."
  print(*items, end=' ', flush=flush)

def outL(*items: Any, sep='', flush=False) -> None:
  "Write `items` to std out; sep='', end='\\n'."
  print(*items, sep=sep, flush=flush)

def outN(*items: Any, sep='', flush=False) -> None:
  "Write `items` to std out; sep='', end=('' if items and items[-1].endswith('\\n') else '\\n')."
  end = ('' if items and items[-1].endswith('\n') else '\n')
  print(*items, sep=sep, end=end, flush=flush)

def outSL(*items: Any, flush=False) -> None:
  "Write `items` to std out; sep=' ', end='\\n'."
  print(*items, flush=flush)

def outSN(*items: Any, flush=False) -> None:
  "Write `items` to std out; sep='', end=('' if items and items[-1].endswith('\\n') else '\\n')."
  end = ('' if items and items[-1].endswith('\n') else '\n')
  print(*items, sep=' ', end=end, flush=flush)

def outLL(*items: Any, flush=False) -> None:
  "Write `items` to std out; sep='\\n', end='\\n'."
  print(*items, sep='\n', flush=flush)

def outLSSL(*items: Any, flush=False) -> None:
  "Write `items` to std out; sep='\\n  ', end='\\n'."
  print(*items, sep='\n  ', flush=flush)

def outP(*items: Any, label=None, flush=False, **opts: Any) -> None:
  'Pretty print to std out.'
  writeP(stdout, *items, label=label, **opts)


# std err.

def errZ(*items: Any, sep='', end='', flush=False) -> None:
  "Write items to std err; default sep='', end=''."
  print(*items, sep=sep, end=end, file=stderr, flush=flush)

def errS(*items: Any, sep='', flush=False) -> None:
  "Write items to std err; sep='', end=' '."
  print(*items, sep=sep, end=' ', file=stderr, flush=flush)

def errSZ(*items: Any, flush=False) -> None:
  "Write items to std err; sep=' ', end=''."
  print(*items, sep=' ', end='', file=stderr, flush=flush)

def errSS(*items: Any, flush=False) -> None:
  "Write items to std err; sep=' ', end=''."
  print(*items, sep=' ', end=' ', file=stderr, flush=flush)

def errL(*items: Any, sep='', flush=False) -> None:
  "Write items to std err; sep='', end='\\n'."
  print(*items, sep=sep, end='\n', file=stderr, flush=flush)

def errN(*items: Any, sep='', flush=False) -> None:
  "Write `items` to std err; sep='', end=('' if items and items[-1].endswith('\\n') else '\\n')."
  end = ('' if items and items[-1].endswith('\n') else '\n')
  print(*items, sep=sep, end=end, file=stderr, flush=flush)

def errSL(*items: Any, flush=False) -> None:
  "Write items to std err; sep=' ', end='\\n'."
  print(*items, sep=' ', end='\n', file=stderr, flush=flush)

def errSN(*items: Any, flush=False) -> None:
  "Write `items` to std err; sep='', end=('' if items and items[-1].endswith('\\n') else '\\n')."
  end = ('' if items and items[-1].endswith('\n') else '\n')
  print(*items, sep=' ', end=end, file=stderr, flush=flush)

def errLL(*items: Any, flush=False) -> None:
  "Write items to std err; sep='\\n', end='\\n'."
  print(*items, sep='\n', end='\n', file=stderr, flush=flush)

def errLSSL(*items: Any, flush=False) -> None:
  "Write items to std err; sep='\\n  ', end='\\n'."
  print(*items, sep='\n  ', end='\n', file=stderr, flush=flush)

def errP(*items: Any, label=None, **opts) -> None:
  'Pretty print to std err.'
  writeP(stderr, *items, label=label, **opts)


def err_progress(iterable: Iterable[_T], label='progress', suffix='', final_suffix='', frequency:Union[float, int]=0.1, limit=0) -> Iterator[_T]:
  '''
  For interactive terminals, return a generator that yields the elements of `iterable`
  and displays a progress indicator on std err.
  '''
  assert frequency >= 0
  if not frequency or not stderr.isatty():
    return iter(iterable)

  ERASE_LINE = '\x1b[2K'

  if label is None:
    label = str(iterable)
  pre = f'{ERASE_LINE}\r◊ {label}: '
  post = (suffix and ' ' + suffix) + '…'
  final = f' {final_suffix}.' if final_suffix else '.'

  if isinstance(frequency, float):
    from time import time
    def err_progress_gen() -> Iterator[_T]:
      prev_t = time()
      step = 1
      next_i = step
      i = -1
      for i, el in enumerate(iterable):
        if limit and i == limit:
          i -= 1
          break
        if i == next_i:
          print(f'{pre}{i:,}{post}', end='', file=stderr, flush=True)
          t = time()
          d = t - prev_t
          step = max(1, int(step * frequency / d))
          prev_t = t
          next_i = i + step
        yield el
      print(f'{pre}{i+1:,}{final}', file=stderr)


  else:
    def err_progress_gen() -> Iterator[_T]:
      for i, el in enumerate(iterable):
        if limit and i == limit:
          i -= 1
          break
        if i % frequency == 0:
          print(pre + str(i) + post, end='', file=stderr, flush=True)
        yield el
      print(pre + str(i) + final, file=stderr)

  return err_progress_gen()


# convenience read/write.


def read_from_path(path: str, default: str=None) -> str:
  'Read all text from file at `path`.'
  try:
    with open(path) as f:
      return f.read()
  except (FileNotFoundError, IsADirectoryError):
    if default is None: raise
    return default

def read_line_from_path(path: str, line0=0, keep_end=False, default: str=None) -> str:
  'Read a single line of text from file at `path`.'
  try:
    with open(path) as f:
      for i, line in enumerate(f):
        if i == line0:
          return line if keep_end else line.rstrip('\n')
      if default is None: raise IndexError(line0)
      return default
  except (FileNotFoundError, IsADirectoryError, PermissionError, UnicodeDecodeError):
    if default is None: raise
    return default

def write_to_path(path: str, string) -> None:
  'Writes `string` to file at `path`.'
  with open(path, 'w') as f:
    f.write(string)


# Opener utility.

def mk_opener(flags:int, mode=0o777, dir_fd:int=None) -> Callable[[str, int], int]:
  def _opener(path:str, _flags:int, mode=mode, dir_fd=dir_fd) -> int: return os_open(path,_flags&flags)
  return _opener

nonblock_opener = mk_opener(O_NONBLOCK)


# Nonblocking tools.

class AsyncLineReader(ContextManager):
  '''
  A file-like object for reading asynchronously from a file descriptor.
  '''

  def __init__(self, path:str) -> None:
    self.fd = os_open(path, O_RDONLY|O_NONBLOCK) # TODO: accept raw descriptor.
    self.buffer = bytearray()

  def __del__(self) -> None:
    self.close()

  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> None:
    self.close()

  def close(self) -> None:
    if self.fd >= 0:
      os_close(self.fd)
      self.fd = -1

  def readline(self) -> str:
    '''
    Attempt to return a complete line from the input stream.
    If there is not enough data available, return ''.
    '''
    line:Union[bytes,bytearray]

    # The buffer might already contain a complete line.
    buffer_line_end = self.buffer.find(0x0a) + 1 # 0 if no newline found.
    if buffer_line_end: # Buffer already contains a complete line.
      line = self.buffer[:buffer_line_end]
      del self.buffer[buffer_line_end:]
      return line.decode()

    # Read from the file descriptor until it returns nothing or we have a complete line.
    while True:
      try: data = os_read(self.fd, 4096)
      except BlockingIOError: return ''
      if not data: return ''
      line_end = data.find(0x0a) + 1 # 0 if no newline found.
      if not line_end: # No newline.
        self.buffer.extend(data)
        continue
      if self.buffer: # Have previous data.
        line_end += len(self.buffer)
        self.buffer.extend(data)
        line = self.buffer[:line_end]
        del self.buffer[:line_end]
      else: # No previous data.
        line = data[:line_end]
        self.buffer.extend(data[line_end:])
      return line.decode()


# misc.

def clip_newlines(iterable: Iterable[str]) -> Iterable[str]:
  for line in iterable:
    yield line.rstrip('\n')


def confirm(question:str) -> bool:
  from .term import CBreakMode
  print(f'{question}? press "y" to confirm: ', end='', flush=True)
  with CBreakMode():
    response = stdin.read(1)
    print(response)
    return (response == 'y')


def assert_eq(a: Any, b: Any):
  if a != b:
    raise AssertionError(f'not equal:\n  {a!r}\n  {b!r}')


def tee_to_err(iterable:Iterable[_T], label:str = 'tee_to_err') -> Iterator[_T]:
  for el in iterable:
    errL(label, ': ', repr(el))
    yield el
