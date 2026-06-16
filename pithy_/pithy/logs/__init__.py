# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import AbstractContextManager, ContextDecorator
from io import TextIOWrapper
from json import dumps as render_json
from logging import Formatter, LogRecord
from sys import stderr, stdout
from traceback import TracebackException
from types import TracebackType
from typing import Any, get_args, Literal

from ..ansi import RST, TXT_C, TXT_G, TXT_M, TXT_N, TXT_R, TXT_Y
from ..date import DateTime
from ..encode import encode_obj
from ..json import JsonDict, parse_json
from ..strings import identifier_or_repr
from ..type_utils import req_type
from ..typing_utils import OptBaseExc, OptTraceback, OptTypeBaseExc


'''
A lightweight logging system.
'''

LogLevel = Literal['debug', 'info', 'warn', 'error']

log_levels:tuple[str,...] = get_args(LogLevel)

log_level_colors = {
  'debug': TXT_C,
  'info': TXT_G,
  'warn': TXT_Y,
  'error': TXT_R,
  'other': TXT_M,
}

std_log_levels_simplified:dict[str,LogLevel] = {
  'NOTSET': 'error',
  'DEBUG': 'debug',
  'INFO': 'info',
  'WARNING': 'warn',
  'ERROR': 'error',
  'CRITICAL': 'error',
}


log_file = stdout

try: is_log_tty = log_file.isatty()
except AttributeError: is_log_tty = False


def logD(_:str, **kwargs:Any) -> None:
  '''
  Log a debug message.
  '''
  _log('debug', _, **kwargs)


def logI(_:str, **kwargs:Any) -> None:
  '''
  Log an info message.
  '''
  _log('info', _, **kwargs)


def logW(_:str, **kwargs:Any) -> None:
  '''
  Log a warning message.
  '''
  _log('warn', _, **kwargs)


def logE(_:str, **kwargs:Any) -> None:
  '''
  Log an error message.
  '''
  _log('error', _, **kwargs)


def log(level:str, _:str, **kwargs:Any) -> None:
  '''
  Log a message at the given level with optional key-value pairs.
  '''
  if level not in log_levels: print(render_log_fn('info', f'Invalid log level: {level}.'))
  print(render_log_fn(level, _, **kwargs), flush=True)


def _log(level:str, _:str, **kwargs:Any) -> None:
  '''
  Internal log function that chooses render function and flushes output.
  '''
  print(render_log_fn(level, _, **kwargs), flush=True)


def render_log_text(level:str, _:str='', exc:BaseException|None=None, **kwargs:Any) -> str:
  '''
  Log a message at the given level with optional key-value pairs.
  The output format is logfmt.
  '''
  msg = (' ' + _) if _ else ''
  pairs = '  '.join(f'{TXT_N}{identifier_or_repr(k)}{RST}:{v!r}' for k, v in kwargs.items())
  if pairs: pairs = '  ' + pairs
  clr = log_level_colors.get(level, '')
  rst = RST if clr else ''
  exc_text = ''
  if exc is not None:
    exc_text = f'\n{fmt_exc_text(exc)}'

  return f'{clr}{level}{rst}:{msg}{pairs}{exc_text}'


def render_log_json(level:str, _:str='', exc:BaseException|None=None, **kwargs:Any) -> str:
  '''
  Render a log message as a JSON string.
  '''
  # Construct the log record so that level and message are rendered first.
  items:dict[str,Any] = {'level': level}
  if _: items['_'] = _
  if exc is not None:
    items['exc'] = fmt_exc_json(exc)
  items.update(kwargs)
  return render_json(items, ensure_ascii=False, indent=None, separators=(',', ':'), default=encode_obj)


render_log_fn = render_log_text if is_log_tty else render_log_json


def fmt_exc_text(exc:BaseException) -> str:
  '''
  Format exception information as text.
  '''
  te = TracebackException.from_exception(exc).format(colorize=True) # type: ignore[call-arg]
  return ''.join(te)


def fmt_exc_json(exc:BaseException) -> list[str]:
  '''
  Format exception information as a JSON-serializable dict.
  '''
  return list(TracebackException.from_exception(exc).format(colorize=True)) # type: ignore[call-arg]


# Rendering stored logs.

def render_log_record_as_text(record:str|JsonDict, infer_journald:bool=True) -> str:
  'Format an in-memory JSON record (unparsed str or parsed dict) as human-readable text.'

  if isinstance(record, str):
    parsed = parse_json(record)
    if not isinstance(parsed, dict):
      raise TypeError(f'render_log_record_as_text expected JSON dict; received: {parsed!r}')
    record = parsed

  if infer_journald and 'level' not in record and 'MESSAGE' in record: # Looks like a journald record.
    return render_journald_record_as_text(record)

  level = req_type(record.get('level', 'other'), str)
  msg = req_type(record.get('_', ''), str)

  # Note: exc is stored as pre-formatted lines in JSON, so we catenate it separately.
  exc_lines = req_type(record.get('exc', []), list[str])
  kwargs = {k:v for k, v in record.items() if k not in ('level', '_', 'exc')}

  text = render_log_text(level, msg, exc=None, **kwargs)
  if exc_lines:
    text += '\n' + ''.join(exc_lines)
  return text


def render_journald_record_as_text(record:JsonDict) -> str:
  keys = set(record)

  ts = ''
  if '__REALTIME_TIMESTAMP' in keys:
    rtts = req_type(record['__REALTIME_TIMESTAMP'], str)
    try: ts = DateTime.fromtimestamp(int(rtts)/1_000_000).isoformat(sep=' ')
    except Exception: pass
    else: keys.remove('__REALTIME_TIMESTAMP')

  msg = ''
  if 'MESSAGE' in keys:
    message = req_type(record['MESSAGE'], str) # TODO: journald can output an array of numbers for non-utf8.
    if message.startswith('{') and message.endswith('}'): # Looks like JSON.
      try: msg = render_log_record_as_text(message, infer_journald=False)
      except Exception: pass
      else: keys.remove('MESSAGE')

  if keys:
    # Journald emits unordered json records so we sort them.
    sorted_keys = sorted(keys, key=lambda k: k.replace('_', ' ')) # Make underscore sort before capital letters.
    pairs = '  '.join(f'{TXT_N}{identifier_or_repr(k)}{RST}:{record[k]!r}' for k in sorted_keys)
    return f'{ts}  {pairs}  {msg}'.strip()
  else:
    return f'{ts}  {msg}'.strip()




# excepthooks.

def main_excepthook(exc_type:type[BaseException], exc_value:BaseException, traceback:TracebackType|None) -> None:
  'Logging function for sys.excepthook. Note that only the exc_value is used.'
  logE('Uncaught exception', exc=exc_value)


def threading_excepthook(args:Any) -> None:
  'Logging function for threading.excepthook.'
  logE('Uncaught threading exception', exc=args.exc_value)


def install_excepthooks() -> None:
  'Install both sys and threading excepthooks.'
  import sys
  import threading
  sys.excepthook = main_excepthook
  threading.excepthook = threading_excepthook


# stdlib warnings formatting.

def formatwarning(message:Warning|str, category:type[Warning], filename:str, lineno:int, line:str|None=None) -> str:
  '''
  Override for warnings.formatwarning to produce pithy-style warning messages.
  '''
  return render_log_fn('warn', str(message), type=category.__name__, loc=f'{filename}:{lineno}') + '\n'


def install_warnings_formatter() -> None:
  '''
  Install the pithy warnings formatter.
  '''
  import warnings
  warnings.formatwarning = formatwarning


def configure_stdio_for_line_logging() -> None:
  'Ensure log output is flushed per-line when stdout/stderr are not TTYs.'
  if not stdout.isatty() and isinstance(stdout, TextIOWrapper): stdout.reconfigure(line_buffering=True)
  if not stderr.isatty() and isinstance(stderr, TextIOWrapper): stderr.reconfigure(line_buffering=True)



class PithyLogFormatter(Formatter):
  '''
  A very simple log formatter for use with the python standard logging module.
  '''

  def format(self, record:LogRecord) -> str:
    level = std_log_levels_simplified.get(record.levelname, 'error')

    if is_log_tty:
      try: msg_fmt = getattr(record, 'color_message') # Note: this is probably Uvicorn-specific; should be refactored.
      except AttributeError: msg_fmt = record.msg
    else:
      msg_fmt = record.msg

    msg = (msg_fmt % record.args) if record.args else msg_fmt

    extra_fields = self.get_extra_fields(record)

    if exc_info := record.exc_info:
      extra_fields['exc'] = exc_info[1]

    return render_log_fn(level, _=msg, **extra_fields)


  def get_extra_fields(self, record:LogRecord) -> dict[str,Any]:
    '''
    Get extra fields from the log record.
    '''
    return {k:v for k,v in vars(record).items() if k not in _std_LogRecord_fields}


_std_LogRecord_fields = set(vars(LogRecord('name', 0, 'pathname', 0, 'msg', (), None)).keys())
_std_LogRecord_fields.add('color_message')


class log_exc_and_suppress(AbstractContextManager, ContextDecorator):
  '''
  Context manager to catch and suppress specified exceptions, logging the exceptions.

  After the exception is logged, execution proceeds with the next statement following the with statement.

  This context manager can also be used as a decorator.

  This implementation is derived from the `suppress` context manager in the Python standard library.
  '''

  def __init__(self, *exceptions:type[BaseException]) -> None:
    self._exceptions = exceptions

  def __enter__(self) -> log_exc_and_suppress:
    return self

  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> bool:
    if exc_type is None: return False
    if issubclass(exc_type, self._exceptions):
      logE('exception suppressed', exc=exc_value)
      return True
    if isinstance(exc_value, BaseExceptionGroup):
      _, rest = exc_value.split(self._exceptions)
      if rest is None: # Every leaf matched: report the whole group and suppress.
        logE('exception suppressed', exc=exc_value)
        return True
      return False # Some leaf did not match: propagate the original group unchanged.
    return False
