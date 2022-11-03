# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from typing import Any


def repr_clean(obj:Any) -> str:
  '''
  Attempt to ensure that an object gets printed with a decent repr.
  Some third-party libraries print unconventional reprs that are confusing inside of collection descriptions.
  '''
  r = repr(obj)
  if type(obj) in _literal_repr_types or _decent_repr_re.fullmatch(r): return r
  return f'{type(obj).__name__}({r})'

_literal_repr_types = { bytes,str,list,dict,set,tuple }
_decent_repr_re = re.compile(r'[a-zA-Z][.\w]*\(.*\)')


def repr_lim(obj:Any, limit=64) -> str:
  r = repr(obj)
  if limit > 2 and len(r) > limit:
    q = r[0]
    if q in '\'"': return f'{r[:limit-2]}{q}…'
    else: return f'{r[:limit-1]}…'
  return r
