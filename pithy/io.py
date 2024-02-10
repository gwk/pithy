# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import close as os_close, O_NONBLOCK, O_RDONLY, open as os_open, read as os_read
from pprint import pprint
from shlex import quote as sh_quote
from string import Template as _Template
from sys import stderr, stdin, stdout
from typing import Any, Callable, cast, ContextManager, Iterable, Iterator, Sized, TextIO, TypeVar

from .desc import errD, outD, writeD
from .reprs import repr_ml
from .typing import OptBaseExc, OptTraceback, OptTypeBaseExc


errD = errD
outD = outD
writeD = writeD


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

def writeTF(file:TextIO, template_fmt:str, *items:Any, flush=False, **keyed_items:Any) -> None:
  """
  Expand the format string with keyed_items, then format the string; end=''.
  Useful for constructing dynamic format strings.
  """
  fmt = _Template(template_fmt).substitute(**keyed_items)
  print(fmt.format(*items, **keyed_items, end='', file=file, flush=flush))


def writeTFL(file:TextIO, template_fmt:str, *items:Any, flush=False, **keyed_items:Any) -> None:
  """
  Expand the format string template with keyed_items, then format the string; end='\\n'
  Useful for constructing dynamic format strings.
  """
  fmt = _Template(template_fmt).substitute(**keyed_items)
  print(fmt.format(*items, **keyed_items, file=file, flush=flush))


# Pretty printing.

def writeP(file:TextIO, *labels_and_obj: Any, indent=2, **opts:Any) -> None:
  'Write labels and pretty-print object to file.'
  labels = labels_and_obj[:-1]
  obj = labels_and_obj[-1]
  if labels: print(*labels, end=': ', file=file)
  pprint(obj, stream=file, indent=indent, **opts)


def writeM(file:TextIO, *labels_and_obj:Any, at_line_start:bool|None=None, color:bool|None=None, **opts:Any) -> None:
  'Write labels and multiline repr of object to file.'
  labels = labels_and_obj[:-1]
  obj = labels_and_obj[-1]
  if labels: print(*labels, end=': ', file=file)
  if at_line_start is None: at_line_start = not labels
  if color is None: color = file.isatty()
  print(repr_ml(obj, at_line_start=at_line_start, color=color, **opts), file=file)


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

def outR(*items: Any, sep='', is_tty:bool|None=None, flush=False) -> None:
  '''
  Write `items` to std out. sep=''.
  If `is_tty`, end=ERASE_LINE_F+'\\r'; otherwise, end='\\n'.
  If `is_tty` is None, it defaults to stdout.isatty().
  '''
  if is_tty is None: is_tty = stdout.isatty()
  print(*items, sep=sep, end=('\x1b[0K\r' if is_tty else '\n'), flush=flush)

def outSR(*items: Any, is_tty:bool|None=None, flush=False) -> None:
  '''
  Write `items` to std out; sep=' '.
  If `is_tty`, end=ERASE_LINE_F+'\\r'; otherwise, end='\\n'.
  If `is_tty` is None, it defaults to stdout.isatty().
  '''
  if is_tty is None: is_tty = stdout.isatty()
  print(*items, sep=' ', end=('\x1b[0K\r' if is_tty else '\n'), flush=flush)

def outP(*labels_and_obj:Any, **opts: Any) -> None:
  'Pretty print to std out.'
  writeP(stdout, *labels_and_obj, **opts)

def outM(*labels_and_obj:Any, **opts: Any) -> None:
  'Multiline repr to std out.'
  writeM(stdout, *labels_and_obj, **opts)


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

def errP(*labels_and_obj:Any, **opts) -> None:
  'Pretty print to std err.'
  writeP(stderr, *labels_and_obj, **opts)

def errM(*labels_and_obj:Any, **opts) -> None:
  'Multiline repr to std err.'
  writeM(stderr, *labels_and_obj, **opts)


def err_progress(iterable: Iterable[_T], label='progress', *, suffix='', final_suffix='', every:int=1, frequency:float=0.1,
 limit=0) -> Iterator[_T]:
  '''
  For interactive terminals, return a generator that yields the elements of `iterable`
  and displays a progress indicator on std err.
  If `frequency` is > 0, print a message every `frequency` seconds.
  Otherwise, print a message every `every` elements.
  If either `frequency` or `every` are 0, or stderr is not a TTY, return `iterable` unchanged.
  '''
  if not (every >= 0): raise ValueError(f'every must be >= 0; received {every!r}.')
  if not (frequency >= 0): raise ValueError(f'frequency must be >= 0; received {frequency!r}.')

  if every == 0 or frequency == 0 or not stderr.isatty():
    return iter(iterable)

  ERASE_LINE = '\x1b[2K'

  if label is None:
    label = str(iterable)
  pre = f'{ERASE_LINE}\r◊ {label}: '
  post = (suffix and ' ' + suffix) + '…'
  final = f' {final_suffix}.' if final_suffix else '.'

  total = ''
  width = 0
  try: l = len(cast(Sized, iterable))
  except TypeError: pass
  else:
    ls = f'{l:,}'
    width = len(ls)
    total = '/' + ls

  if frequency > 0:
    from time import monotonic as timer  # on macOS, monotomic and perf_counter both perform slightly better than `time`.

    # On macOS, calling the timer on every iteration induces ~1.3x overhead for a `x += 1` loop,
    # compared to the same loop with a very large integer frequency.
    # Since most loop bodies are more expensive, this seems broadly acceptable.
    # However, if the user wants to reduce this overhead, they can specify both `every` and `frequency`.
    # In that case, we check only check the timer every `every` iterations.

    if every == 1:
      def err_progress_gen_frequency() -> Iterator[_T]:
        prev_t = -1.0
        completed_count = 0
        for el in iterable:
          if limit and completed_count == limit: break
          t = timer()
          d = t - prev_t
          if d >= frequency:
            print(f'{pre}{completed_count:{width},}{total}{post}', end='', file=stderr, flush=True)
            prev_t = t
          yield el
          completed_count += 1
        print(f'{pre}{completed_count:{width},}{total}{final}', file=stderr)
      return err_progress_gen_frequency()

    else:
      def err_progress_gen_frequency_every() -> Iterator[_T]:
        prev_t = -1.0
        completed_count = 0
        for el in iterable:
          if limit and completed_count == limit: break
          if completed_count % every == 0:
            t = timer()
            d = t - prev_t
            if d >= frequency:
              print(f'{pre}{completed_count:{width},}{total}{post}', end='', file=stderr, flush=True)
              prev_t = t
          yield el
          completed_count += 1
        print(f'{pre}{completed_count:{width},}{total}{final}', file=stderr)
      return err_progress_gen_frequency_every()

  def err_progress_gen_every() -> Iterator[_T]:
    completed_count = 0
    for el in iterable:
      if limit and completed_count >= limit: break
      if completed_count % every == 0:
        print(f'{pre}{completed_count:{width},}{total}{post}', end='', file=stderr, flush=True)
      yield el
      completed_count += 1
    print(f'{pre}{completed_count:{width},}{total}{final}', file=stderr)
  return err_progress_gen_every()


# convenience read/write.


def read_from_path(path: str, default: str|None=None) -> str:
  'Read all text from file at `path`.'
  try:
    with open(path) as f:
      return f.read()
  except (FileNotFoundError, IsADirectoryError):
    if default is None: raise
    return default


def read_line_from_path(path: str, line_index=0, keep_end=False, default: str|None=None) -> str:
  'Read a single line of text from file at `path`.'
  try:
    with open(path) as f:
      for i, line in enumerate(f):
        if i == line_index:
          return line if keep_end else line.rstrip('\n')
      if default is None: raise IndexError(line_index)
      return default
  except (FileNotFoundError, IsADirectoryError, PermissionError, UnicodeDecodeError):
    if default is None: raise
    return default


def write_to_path(path:str, text:str|bytes|bytearray) -> None:
  'Writes `string` to file at `path`.'
  if isinstance(text, str):
    with open(path, 'w') as f: f.write(text)
  else:
    with open(path, 'wb') as bf: bf.write(text)


# Opener utility.

def mk_opener(flags:int, mode=0o777, dir_fd:int|None=None) -> Callable[[str, int], int]:
  def _opener(path:str, _flags:int, mode=mode, dir_fd=dir_fd) -> int: return os_open(path,_flags&flags)
  return _opener

nonblock_opener = mk_opener(O_NONBLOCK)


# Nonblocking tools.

class AsyncLineReader(ContextManager):
  '''
  A file-like object for reading asynchronously from a file descriptor.
  '''

  def __init__(self, path:str):
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
    line:bytes|bytearray

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

def clip_newlines(iterable:Iterable[str]) -> Iterable[str]:
  for line in iterable:
    yield line.rstrip('\n')


def confirm(question:str) -> bool:
  '''
  Prompt the user to confirm a question with a "y" response.
  "y" returns True; any other response returns False.
  The question is printed to stdout, followed by a question mark and prompt.
  '''
  from .term import CBreakMode
  print(f'{question}? press "y" to confirm: ', end='', flush=True)
  with CBreakMode(): response = stdin.read(1)
  print(response)
  return (response == 'y')


def confirm_or_exit(question:str) -> None:
  '''
  Prompt the user to confirm a question with a "y" response.
  "y" returns; any other response exits with status 1.
  The question is printed to stdout, followed by a question mark and prompt.
  '''
  try:
    if not confirm(question): exit(1)
  except KeyboardInterrupt: exit(1)


def assert_eq(a: Any, b: Any):
  if a != b:
    raise AssertionError(f'not equal:\n  {a!r}\n  {b!r}')


def shell_cmd_str(cmd:Iterable[str]) -> str:
  return ' '.join(sh_quote(word) for word in cmd)


def tee_to_err(iterable:Iterable[_T], label:str='tee_to_err', transform:Callable[[_T],Any]|None=None) -> Iterator[_T]:
  for el in iterable:
    s = repr(el) if transform is None else str(transform(el))
    errL(label, ': ', s)
    yield el
