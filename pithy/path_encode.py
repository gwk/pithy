# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from enum import Enum
from .path import path_join, norm_path
from urllib.parse import urlunsplit, urlsplit


def path_encode(string:str) -> str:
  '''
  Encode string into a path.
  Path encoding is similar to url percent encoding, but uses '+' as the indicator character.
  It is used to create convenient file names out of urls.
  Like url encoding, letters, digits, and the characters '_.-' are left unescaped.
  A leading '.' is escaped to prevent hidden files from being created.
  '%' characters are not escaped, to make prior url encoding more readable.
  '/' is translated to ',', which allows multiple path segments in the url to be squashed into a single filename.
  Note that ',' is itself encoded, so the encoding is unambiguous.
  All other bytes are encoded as "+XX", where XX is the uppercase hexadecimal byte value.
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

for c in '%-._':
  _path_encode_table[ord(c)] = c

for start, last in ['09', 'AZ', 'az']:
  for code in range(ord(start), ord(last) + 1):
    _path_encode_table[code] = chr(code)


class PartMode(Enum):
  OMIT = 0
  SQUASH = 1
  COMP = 2

OMIT = PartMode.OMIT
SQUASH = PartMode.SQUASH
COMP = PartMode.COMP


def path_for_url(url:str, *, normalize=True, split_path=True, lead_path_slash=False,
 scheme=OMIT, host=COMP, path=COMP, query=SQUASH, fragment=OMIT) -> str:
  '''
  Return a path encoded from a url by first splitting the url into parts
  and then applying `path_encode` to each part.
  Empty parts are represented by a bare '+'.

  `split_path`: if True, the path is translated into nested directories.
  Otherwise, slashes are translated into commas.

  `scheme`, `host`, `path`, `query`, `fragment` are all tristate PartMode flags.
  * `OMIT` causes that part to be omitted;
  * `SQUASH` causes it to be squashed into the previous path component;
  * `COMP` causes it to be appended as a distinct path component.

  Need to preserve slashes.
  '''

  parts = urlsplit(url) # returns five-element namedtuple.
  comps = []
  def add_comp(mode:PartMode, part:str, prefix='') -> None:
    if mode is OMIT:
      return
    elif mode is COMP:
      comps.append(part)
    elif mode is SQUASH:
      if comps:
        comps[-1] = f'{comps[-1]}{prefix}{part}'
      else:
        comps.append(f'{prefix}{part}')
    else:
      raise NotImplementedError

  add_comp(scheme, parts.scheme)
  add_comp(host, parts.netloc, prefix=('://' if comps else '//'))

  p = parts.path
  if p and normalize: p = norm_path(parts.path) # Do not normalize '' -> '.'.
  if not lead_path_slash and p.startswith('/') and len(p) > 1:
    p = p[1:]
  if split_path and path is COMP:
    comps.extend(p.split('/'))
  else:
    add_comp(path, p)

  if parts.query:
    add_comp(query, parts.query, prefix='?')
  if parts.fragment:
    add_comp(fragment, parts.fragment, prefix='#')

  res = path_join(*[path_encode(c) if c else '+' for c in comps])
  assert res
  assert res[0] != '/'
  return res


def norm_url(url:str) -> str:
  scheme, host, path, query, fragment = urlsplit(url)
  return urlunsplit((scheme, host, norm_path(path), query, fragment))
