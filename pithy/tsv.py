# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Iterable

from .unicode.control_pictures import c0_del_to_pictures


'''
A simple, lossy TSV implementation that uses unicode control pictures to escape control characters.
When parsing it is impossible to distinguish between original control pictures and those used for escaping.
On the other hand, this makes the output much easier to read in practice.

For the unicode control pictures block, see: https://www.unicode.org/charts/PDF/U2400.pdf.
'''


def esc_tsv(s:str) -> str:
  if all(c >= ' ' for c in s): return s
  return ''.join(c0_del_to_pictures.get(c, c) for c in s)


def render_tsv_row(row:Iterable[Any], end:str='\n') -> str:
  return '\t'.join(esc_tsv(str(v)) for v in row) + end


def render_tsv(rows:Iterable[Iterable[Any]]) -> str:
  return ''.join(render_tsv_row(row) for row in rows)


def write_tsv(f:Any, rows:Iterable[Iterable[Any]]) -> None:
  for row in rows:
    f.write(render_tsv_row(row))


def parse_tsv(f:Iterable[str], *, has_header:bool=False, cols:Iterable[str]|None=None) -> Iterable[list[str]]:
  '''
  Parse a file or iterable of lines as TSV. `parse_tsv` performs no unescaping.
  If `has_header` is true, the first line is treated as a header row and skipped.
  If `cols` is given, it is treated as the expected header row and compared against the actual header row.
  '''
  if isinstance(f, str):
    f = f.splitlines()
    it = iter(f)
  else:
    it = (line.rstrip('\n\r') for line in f)

  if has_header:
    try: header_line = next(it)
    except StopIteration: pass
    else:
      header:list[str] = header_line.split('\t')
      if cols is not None: # Match expected header against actual.
        col_names = list(cols)
        if header != col_names:
          raise ValueError(f'parse_tsv expected header row:\n{col_names}\nreceived:\n{header}')

  for line in it:
    yield line.split('\t')
