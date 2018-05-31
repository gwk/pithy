# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from enum import Enum
from os.path import join as path_join, split as path_split
import urllib.parse as _parse


_path_encode_table = [f'+{i:02x}' for i in range(0x100)]

def _preserve(start:str, last:str) -> None:
  for code in range(ord(start), ord(last) + 1):
    _path_encode_table[code] = chr(code)

_preserve('0', '9')
_preserve('A', 'Z')
_preserve('a', 'z')

for c in '%-._': _path_encode_table[ord(c)] = c
_path_encode_table[ord('/')] = ','


def path_encode(string: str) -> str:
  '''
  Encode string into a path.
  Path encoding is similar to url percent encoding, but uses '+' as the indicator character.
  It is used to create convenient file names out of urls.
  Like url encoding, letters, digits, and the characters '_.-' are left unescaped.
  '%' characters are not escaped, to make prior url encoding more readable.
  '/' is translated to ',', which allows multiple path segments in the url to be squashed into a single filename.
  Note that ',' is itself encoded, so the encoding is unambiguous.
  All other bytes are encoded as "+XX", where XX is the uppercase hexadecimal byte value.
  '''
  utf8 = string.encode()
  return ''.join(_path_encode_table[b] for b in utf8)


class PartMode(Enum):
  OMIT = 0
  SQUASH = 1
  COMP = 2

OMIT = PartMode.OMIT
SQUASH = PartMode.SQUASH
COMP = PartMode.COMP


def path_for_url(url:str, *, split_path=False, scheme=OMIT, host:PartMode=COMP,
 path:PartMode=COMP, query:PartMode=SQUASH, fragment:PartMode=OMIT) -> str:
  '''
  Return a path encoded from a url by first splitting the url into parts
  and then applying `path_encode` to each part.
  Empty parts are represented by a bare '+'.

  `split_path`: if True, the path is translated into nested directories.
  Otherwise, slashes are translated into commas.

  `scheme`, `host`, `path`, `query`, `fragment` are all tristate PartMode flags.
  * `None` causes that part to be omitted;
  * `False` causes it to be squashed into the previous part;
  * `True` causes it to be appended as a distinct part.

  Note that `scheme` cannot be `SQUASH`.
  '''
  parts = _parse.urlsplit(url) # returns five-element namedtuple.
  comps = []
  need_scheme_colon = False
  def add_comp(mode:PartMode, joiner:str, part:str) -> None:
    nonlocal need_scheme_colon
    if mode is COMP:
      comps.append(part)
      need_scheme_colon = False
    elif mode is SQUASH:
      if need_scheme_colon:
        assert len(comps) == 1
        comps[0] += ':'
        need_scheme_colon = False
      if part:
        comps[-1] = f'{comps[-1]}{joiner}{part}'

  if scheme is not OMIT:
    assert scheme is not SQUASH
    comps.append(parts.scheme)
    need_scheme_colon = True
  add_comp(host, '//', parts.netloc)
  if path is not OMIT:
    p = parts.path
    if p.startswith('/') and len(p) != 1: p = p[1:]
    if split_path:
      if path is SQUASH: raise Exception(f'`split_path` is set but `path` is `SQUASH`')
      need_scheme_colon = False
      comps.extend(path_split(p))
    else: add_comp(path, '/', p)
  add_comp(query, '?', parts.query)
  add_comp(fragment, '#', parts.fragment)

  res = path_join(*[path_encode(c) if c else '+' for c in comps])
  assert res
  assert res[0] != '/'
  return res
