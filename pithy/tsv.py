# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Iterable


def esc_tsv(s:str) -> str:
  if any(ord(c) < 0x20 for c in s):
    return repr(s)
  return s


def render_tsv_row(row:Iterable[Any]) -> str:
  return '\t'.join(esc_tsv(str(v)) for v in row)


def render_tsv(rows:Iterable[Iterable[Any]]) -> str:
  return '\n'.join(render_tsv_row(row) for row in rows)
