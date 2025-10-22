# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from json import dump as write_json
from sys import stdout
from typing import Any, Literal

from .encode import encode_obj


'''
This is a very lightweight logging implementation.
'''

LogLevel = Literal['debug', 'info', 'warn', 'error']

log_levels:tuple[str,...] = LogLevel.__args__ # type: ignore[attr-defined]


log_file = stdout

try: is_log_tty = log_file.isatty()
except AttributeError: is_log_tty = False


def logD(_:str, **kwargs:Any) -> None:
  '''
  Log a debug message.
  '''
  log_fn('debug', _, **kwargs)


def logI(_:str, **kwargs:Any) -> None:
  '''
  Log an info message.
  '''
  log_fn('info', _, **kwargs)


def logW(_:str, **kwargs:Any) -> None:
  '''
  Log a warning message.
  '''
  log_fn('warn', _, **kwargs)

def logE(_:str, **kwargs:Any) -> None:
  '''
  Log an error message.
  '''
  log_fn('error', _, **kwargs)


def log(level:str, _:str, **kwargs:Any) -> None:
  '''
  Log a message at the given level with optional key-value pairs.
  '''
  if level not in log_levels: log_fn('info', f'Invalid log level: {level}.')
  log_fn(level, _, **kwargs)


def log_as_text(level:str, _:str='', **kwargs:Any) -> None:
  '''
  Log a message at the given level with optional key-value pairs.
  The output format is logfmt.
  '''
  msg = (' ' + _) if _ else ''
  pairs = '  '.join(f'{k}:{v!r}' for k,v in kwargs.items())
  if pairs: pairs = '  ' + pairs
  print(f'{level}:', msg, pairs, sep='', file=log_file)


def log_as_json(level:str, _:str='', **kwargs:Any) -> None:
  '''
  Log a message at the given level with optional key-value pairs.
  The output format is JSON.
  '''
  # Construct the log record so that level and message are rendered first.
  items = {'level': level}
  if _: kwargs['_'] = _
  items.update(kwargs)
  write_json(items, log_file, ensure_ascii=False, indent=None, separators=(',', ':'), default=encode_obj)
  print(file=log_file)


log_fn = log_as_text if is_log_tty else log_as_json
