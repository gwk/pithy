# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Iterable, Mapping


'''
This is a very lightweight implementation of the logfmt logging format.

Some of the design is inspired by logftmter:
https://github.com/jteppinette/python-logfmter/blob/main/src/logfmter/formatter.py

However it mostly defers to the logfmt implementation in Go:
https://pkg.go.dev/github.com/kr/logfmt#section-documentation
'''


def logfmt_key(key:str) -> str:
  '''
  Convert a key string into a valid logfmt key.
  The Go spec describes valid keys as: any byte greater than ' ', excluding '=' and '"'.
  Since we are dealing with unicode strings instead of byte strings,
  we instead use a translation table for ASCII and latin-1, based on `isprintable`.
  '''

  if not key: return '_'
  return key.translate(_logfmt_key_trans)


_latin1 = tuple(chr(i) for i in range(256))

_logfmt_key_trans = str.maketrans(dict.fromkeys([c for c in _latin1 if (not c.isprintable() or c in ' "=')], '_'))


def logfmt_val(value:Any) -> str:
  try: return logfmt_prim_val_strs[value]
  except KeyError: pass
  if isinstance(value, float): return str(value)
  return logfmt_escape(str(value))


logfmt_prim_val_strs = {
  True: 'true',
  False: 'false',
  None: '',
}


def logfmt_escape(value:str) -> str:
  '''
  Escape a string for logfmt.
  '''
  if value == '': return '""'
  value = value.replace('"', '\\"') # Backslash-escape double quotes.
  value = value.replace('\n', '\\n') # Backslash-escape newlines.
  needs_quotes = ' ' in value or '=' in value
  if needs_quotes: value = f'"{value}"'
  return value


def logfmt_items(items:Iterable[tuple[str,Any]]|Mapping[str,Any]) -> str:
  '''
  Format an iterable or mapping of parameters into a logfmt string.
  '''
  if isinstance(items, Mapping): items = items.items()
  return ' '.join(f'{logfmt_key(k)}={logfmt_val(v)}' for k, v in items)


def logfmt(**kwargs:Any) -> str:
  '''
  Format a logfmt string from keyword arguments.
  '''
  return logfmt_items(kwargs)
