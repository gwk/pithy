# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os.path as _os_path
import urllib.parse as _parse


def _path_encode_byte(b: int) -> str:
  '''
  Path encoding is similar to url percent encoding, but uses '+' as the escape character.
  It is used to create convenient file system paths out of urls.
  Just like url encoding, letters, digits, and the characters '_.-' are left unescaped.
  Additionally, '%' characters are not escaped, to make prior url encoding more readable,
  and '/' is translated to '\\' which makes the results more legible.
  Note that '\\' is itself encoded, so the encoding is unambiguous.
  All other bytes are encoded as "+XX", where XX is the capitalized hexadecimal byte value.

  ascii notes:
  0x25: '%'
  0x2d: '-'
  0x2e: '.'
  0x2f: '/'
  0x30-39: '0'-'9'
  0x41-5a: 'A'-'Z'
  0x5f: '_'
  0x61-7a: 'a'-'z'
  '''
  if \
    (0x30 <= b <= 0x39) or \
    (0x41 <= b <= 0x5a) or \
    (0x61 <= b <= 0x7a) or \
    b in (0x25, 0x2d, 0x2e, 0x5f):
    return chr(b)
  elif b == 0x2f:
    return '\\'
  else:
    return '+{:2X}'.format(b)

_path_encode_table = tuple(_path_encode_byte(b) for b in range(0xff))


def path_encode(string: str) -> str:
  'Encode string into a path.'
  utf8 = string.encode()
  return ''.join(_path_encode_table[b] for b in utf8)


def path_for_url(url: str) -> str:
  'Return a path encoded from a url.'
  parts = _parse.urlsplit(url) # returns five-element namedtuple.
  name = path_encode(''.join((parts.path, parts.query, parts.fragment)))
  return _os_path.join(parts.scheme, path_encode(parts.netloc), name)
