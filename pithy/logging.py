# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from json import dumps as render_json
from sys import stdout
from typing import Any, Literal

from .ansi import RST, TXT_C, TXT_G, TXT_N, TXT_R, TXT_Y
from .encode import encode_obj


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
  pairs = '  '.join(f'{TXT_N}{k}{RST}:{v!r}' for k,v in kwargs.items())
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
