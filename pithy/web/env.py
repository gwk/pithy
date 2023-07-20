# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import environ

from ..transtruct import bool_str_vals


def is_web_dbg() -> bool:
  'Return True if the environment has WEB_DBG set to a common true-like string value.'
  return bool_str_vals[environ.get('WEB_DBG', '0')]


def web_data_dir() -> str:
  'Get the data directory specified by the environment variable WEB_DATA_DIR. Defaults to `./data`.'
  return environ.get('WEB_DATA_DIR', './data')


def web_port() -> int:
  'Get the server port specified by the environment variable WEB_PORT. Defaults to 8000.'
  return int(environ.get('WEB_PORT', '8000'))


def web_host() -> str:
  'Get the web server host name specified by the environment variable WEB_HOST. Defaults to `localhost`.'
  return environ.get('WEB_HOST', 'localhost')


def is_web_https() -> bool:
  'Return True if the environment has WEB_HTTPS set to a common true-like string value.'
  return bool_str_vals[environ.get('WEB_HTTPS', '0')]


def web_external_addr() -> str:
  '''
  Return the external address of the web server, specified by the environment variables WEB_EXTERNAL_ADDR.
  Defaults to the empty string.
  '''
  return environ.get('WEB_EXTERNAL_ADDR', '')


def web_dev_uid() -> int:
  '''
  WEB_DEV_UID is an environment variable that allows for automatic login.
  It is only allowed in development mode.
  '''
  if not is_web_dbg(): return 0 # Disallowed.
  return int(environ.get('WEB_DEV_UID', '0'))
