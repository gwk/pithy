# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from collections.abc import Sequence
from typing import Any, Iterator

from ..ansi import RST_TXT, TXT_B, TXT_C, TXT_D, TXT_G, TXT_M, TXT_R, TXT_Y


class Row(sqlite3.Row, Sequence):
  'A row of a query result. Subclasses sqlite3.Row to add property access.'

  def __getattr__(self, key:str) -> Any:
    try: return self[key]
    except IndexError as e: raise AttributeError(key) from e

  def get(self, key:str, default:Any=None) -> Any:
    try: return self[key]
    except IndexError: return default

  def items(self) -> Iterator[tuple[str, Any]]:
    'Return an iterator of (key, value) pairs.'
    for key in self.keys():
      yield key, self[key]

  def qdi(self) -> str:
    '"quick describe inline". Return a string describing the query result.'
    parts = []
    for key, val in self.items():
      color = _row_qdi_colors.get(type(val), TXT_R)
      parts.append(f'{TXT_D}{key}:{color}{val!r}{RST_TXT}')
    return '  '.join(parts)


_row_qdi_colors = {
  bool: TXT_G,
  bytes: TXT_M,
  float: TXT_B,
  int: TXT_C,
  str: TXT_Y,
  type(None): TXT_R,
}
