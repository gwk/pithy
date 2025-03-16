# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import environ

from ..default import Raise
from ..transtruct import bool_str_vals


def is_web_dbg() -> bool:
  'Return True if the environment has WEB_DBG set to a common true-like string value.'
  return bool_str_vals[environ.get('WEB_DBG', '0')]


def web_data_dir() -> str:
  'Get the data directory specified by the environment variable WEB_DATA_DIR. Defaults to `./data`.'
  return environ.get('WEB_DATA_DIR', './data')


def web_proto() -> str:
  'Get the web server protocol specified by the environment variable WEB_PROTO. Defaults to `http`.'
  return environ.get('WEB_PROTO', 'http')


def web_host() -> str:
  'Get the web server host name specified by the environment variable WEB_HOST. Defaults to `localhost`.'
  return environ.get('WEB_HOST', 'localhost')


def web_port() -> int:
  'Get the server port specified by the environment variable WEB_PORT. Defaults to 8000.'
  return int(environ.get('WEB_PORT', '8000'))


def web_addr() -> str:
  'Get the web server address specified by the environment variables WEB_PROTO, WEB_HOST, and WEB_PORT.'
  return f'{web_proto()}://{web_host()}:{web_port()}'


def web_external_host(default:str|Raise=Raise._) -> str:
  '''
  Get the external web server host name specified by the environment variable WEB_EXTERNAL_HOST.
  This function does not default to `web_host()` because doing so can lead to errors in production.
  If the environment variable is not set, return `default`, or raise KeyError.
  '''
  try:
    return environ['WEB_EXTERNAL_HOST']
  except KeyError:
    if default is Raise._: raise
    return default


def web_external_addr() -> str:
  '''
  Return the external address of the web server, defined to use the "https:" protocol and WEB_EXTERNAL_HOST.
  Raises KeyError if WEB_EXTERNAL_HOST is not set.
  '''
  host = web_external_host()
  if host == 'localhost': return web_addr()
  return f'https://{host}'


def web_dev_uid() -> int:
  '''
  WEB_DEV_UID is an environment variable that allows for automatic login.
  It is only allowed in development mode.
  '''
  if not is_web_dbg(): return 0 # Disallowed.
  return int(environ.get('WEB_DEV_UID', '0'))
