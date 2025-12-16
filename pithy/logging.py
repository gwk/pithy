# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from json import dumps as render_json
from logging import Formatter, LogRecord
from sys import stdout
from typing import Any, Literal

from .ansi import RST, TXT_C, TXT_G, TXT_N, TXT_R, TXT_Y
from .encode import encode_obj
from .string import identifier_or_repr


'''
This is a very lightweight logging implementation.
'''

LogLevel = Literal['debug', 'info', 'warn', 'error']

log_levels:tuple[str,...] = LogLevel.__args__ # type: ignore[attr-defined]

log_level_colors = {
  'debug': TXT_C,
  'info': TXT_G,
  'warn': TXT_Y,
  'error': TXT_R,
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



def render_log_text(level:str, _:str='', **kwargs:Any) -> str:
  '''
  Log a message at the given level with optional key-value pairs.
  The output format is logfmt.
  '''
  msg = (' ' + _) if _ else ''
  pairs = '  '.join(f'{TXT_N}{identifier_or_repr(k)}{RST}:{v!r}' for k, v in kwargs.items())
  if pairs: pairs = '  ' + pairs
  clr = log_level_colors.get(level, '')
  rst = RST if clr else ''
  return f'{clr}{level}{rst}:{msg}{pairs}'


def render_log_json(level:str, _:str='', **kwargs:Any) -> str:
  '''
  Render a log message as a JSON string.
  '''
  # Construct the log record so that level and message are rendered first.
  items = {'level': level}
  if _: items['_'] = _
  items.update(kwargs)
  return render_json(items, ensure_ascii=False, indent=None, separators=(',', ':'), default=encode_obj)


render_log_fn = render_log_text if is_log_tty else render_log_json


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
    return render_log_fn(level, _=msg, **extra_fields)


  def get_extra_fields(self, record:LogRecord) -> dict[str,Any]:
    '''
    Get extra fields from the log record.
    '''
    return {k:v for k,v in vars(record).items() if k not in _std_LogRecord_fields}


_std_LogRecord_fields = set(vars(LogRecord('name', 0, 'pathname', 0, 'msg', (), None)).keys())
_std_LogRecord_fields.add('color_message')
