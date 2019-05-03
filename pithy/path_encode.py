# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from enum import Enum
from urllib.parse import urlsplit, urlunsplit

from .path import norm_path, path_join, path_split


def path_encode(string:str) -> str:
  '''
  Encode string into a path.
  Path encoding is similar to url percent encoding, but uses '+' as the indicator character.
  It is used to create convenient file names out of URLs.
  Like URL encoding, letters, digits, and the characters '_.-' are left unescaped.
  Additionally:
  * A leading '.' is escaped to prevent hidden files from being created.
  * '%' characters are not escaped, to make prior URL encoding more readable.
  * ':' characters are not escaped to make URL schemes more readable.
  * '=' characters are not escaped.
  * '/' is translated to ',', which allows multiple path segments in the url to be squashed into a single filename.
  * Note that ',' is itself encoded, so the encoding is unambiguous.
  * All other bytes are encoded as "+XX", where XX is the uppercase hexadecimal byte value.
  '''
  utf8 = string.encode()
  path = ''.join(_path_encode_table[b] for b in utf8)
  if path.startswith('.'):
    return _encode_dot + path[1:]
  else:
    return path


_encode_dot = f'+{ord("."):02x}'

_path_encode_table = [f'+{i:02x}' for i in range(0x100)]

_path_encode_table[ord('/')] = ','

for c in '%-._:=':
  _path_encode_table[ord(c)] = c

for start, last in ['09', 'AZ', 'az']:
  for code in range(ord(start), ord(last) + 1):
    _path_encode_table[code] = chr(code)


class PartMode(Enum):
  OMIT = 0
  SQUASH = 1
  COMP = 2
  SPLIT = 3

OMIT = PartMode.OMIT
SQUASH = PartMode.SQUASH
COMP = PartMode.COMP
SPLIT = PartMode.SPLIT

def path_for_url(url:str, *, normalize=True,
 scheme=OMIT, host=COMP, path=COMP, query=SQUASH, fragment=OMIT) -> str:
  '''
  Return a path encoded from a url by first splitting the url into parts
  and then applying `path_encode` to each part.
  Empty parts are represented by a bare '+'.

  `split_path`: if True, the path is translated into nested directories.
  Otherwise, slashes are translated into commas.

  `scheme`, `host`, `path`, `query`, `fragment` are all PartMode options.
  * `OMIT` causes that part to be omitted;
  * `SQUASH` causes it to be squashed into the previous path component;
  * `COMP` causes it to be appended as a distinct path component;
  * `SPLIT` is only valid for `path`, and splits the path into components.
  '''

  if scheme in (SQUASH, SPLIT): raise ValueError(f'`scheme` mode cannot be `{scheme.name}`')
  if host == SPLIT: raise ValueError('`host` mode cannot be `SPLIT`')
  if query == SPLIT: raise ValueError('`query` mode cannot be `SPLIT`')
  if fragment == SPLIT: raise ValueError('`fragment` mode cannot be `SPLIT`')


  parts = urlsplit(url) # returns five-element namedtuple.
  comps = []
  def add_comp(mode:PartMode, part:str) -> None:
    if mode is OMIT:
      return
    elif mode is COMP:
      comps.append(part)
    elif mode is SQUASH:
      if comps:
        comps[-1] += part
      else:
        comps.append(part)
    elif mode is SPLIT:
      comps.extend(path_split(part) if part else ['']) # Do not normalize '' -> '.'.
    else:
      raise NotImplementedError

  add_comp(scheme, parts.scheme + ':') # Always include the trailing colon for scheme.

  # The only case where we can omit the host '//' is if neither host nor path is squashed;
  # then host always has its own directory level and the slashes are just noise.
  h = parts.netloc if (host != SQUASH and path != SQUASH and parts.netloc) else ('//' + parts.netloc)
  add_comp(host, h)

  p = parts.path
  if p and normalize: p = norm_path(parts.path) # Do not normalize '' -> '.'.
  # If host has its own directory level and is nonempty then path's leading slash can be omitted, because it must be present.
  if host == COMP and path != SQUASH and parts.netloc and p and p[0] == '/': p = p[1:]
  add_comp(path, p)

  if parts.query:
    add_comp(query, '?' + parts.query)
  if parts.fragment:
    add_comp(fragment, '#' + parts.fragment)

  res = path_join(*[path_encode(c) if c else '+' for c in comps])
  assert res and res[0] != '/', res
  return res


def norm_url(url:str) -> str:
  scheme, host, path, query, fragment = urlsplit(url)
  return urlunsplit((scheme, host, norm_path(path), query, fragment))
