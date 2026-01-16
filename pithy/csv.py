# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# TODO: handle leading UTF8-BOM.

import csv
from csv import Dialect, QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC
from functools import cached_property
from io import StringIO
from sys import stdout
from typing import Any, Callable, Iterable, Iterator, Literal, Mapping, Sequence, TextIO, TypeAlias

from .transtruct import bool_for_val


_convenience_exports = (QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC)

Quoting:TypeAlias = Literal[0, 1, 2, 3, 4, 5]

def write_csv(f:TextIO, *, quoting:Quoting|None=None, header:Sequence[str]|None, rows:Iterable[Sequence]) -> None:
  'Write CSV to a file.'
  if quoting is None: quoting = QUOTE_MINIMAL
  w = csv.writer(f, quoting=quoting)
  if header is not None: w.writerow(header)
  w.writerows(rows)


def out_csv(*, quoting:Quoting|None=None, header:Sequence[str]|None, rows:Iterable[Sequence]) -> None:
  'Write CSV to stdout.'
  write_csv(f=stdout, quoting=quoting, header=header, rows=rows)


def render_csv(*, quoting:Quoting|None=None, header:Sequence[str]|None, rows:Iterable[Sequence]) -> str:
  'Render CSV to a string.'
  with StringIO() as f:
    write_csv(f=f, quoting=quoting, header=header, rows=rows)
    return f.getvalue()


def parse_csv(iterable:Iterable[str], *,
 dialect:str|Dialect|type[Dialect]='excel',
 delimiter:str|None=None,
 doublequote:bool|None=None,
 escapechar:str|None=None,
 quotechar:str|None=None,
 quoting:int=QUOTE_MINIMAL,
 skipinitialspace:bool|None=None,
 strict:bool=True,
 has_header:bool=True,
 row_ctor:Callable|None=None,
 spread_args:bool=False,
 as_dicts:bool=False,
 preserve_empty_vals:bool=False,
 cols:Mapping[str,Callable|None]|None=None) -> 'CsvParser':

  return CsvParser(
    iterable=iterable,
    dialect=dialect,
    delimiter=delimiter,
    doublequote=doublequote,
    escapechar=escapechar,
    quotechar=quotechar,
    quoting=quoting,
    skipinitialspace=skipinitialspace,
    strict=strict,
    has_header=has_header,
    row_ctor=row_ctor,
    spread_args=spread_args,
    as_dicts=as_dicts,
    preserve_empty_vals=preserve_empty_vals,
    cols=cols)


class CsvParser(Iterable):

  def __init__(self, iterable:Iterable[str], *,
   dialect:str|Dialect|type[Dialect]='excel',
   delimiter:str|None=None,
   doublequote:bool|None=None,
   escapechar:str|None=None,
   quotechar:str|None=None,
   quoting:int|None=None,
   skipinitialspace:bool|None=None,
   strict:bool|None=None,
   has_header:bool=True,
   row_ctor:Callable|None=None,
   spread_args:bool=False,
   as_dicts:bool=False,
   remap_keys:dict[str,str]|None=None,
   preserve_empty_vals:bool=False,
   cols:Mapping[str,Callable|None]|None=None) -> None:

    remap_keys = remap_keys or {}

    # Filter out the unspecified options so that the dialect defaults are respected.
    opts:dict[str,Any] = { k : v for (k, v) in [
      ('delimiter', delimiter),
      ('doublequote', doublequote),
      ('escapechar', escapechar),
      ('quotechar', quotechar),
      ('quoting', quoting),
      ('skipinitialspace', skipinitialspace),
      ('strict', strict),
      ] if v is not None }

    if cols is not None:
      # Replace any `bool` types with a useful constructor.
      cols = { k : (bool_for_val if v is bool else v) for k, v in cols.items() }

    if isinstance(iterable, str):
      iterable = iterable.splitlines()

    self._reader = csv.reader(iterable, dialect, **opts)
    self.iterable = iterable
    self.row_ctor = row_ctor
    self.cols = cols
    self.remap_keys = remap_keys

    if has_header:
      try: self.header:list[str]|None = [str(raw_cell) for raw_cell in next(self._reader)]
      except StopIteration: self.header = None # Allow empty files.
      else:
        if cols is not None: # Match expected header against actual.
          col_names = list(cols)
          if self.header != col_names:
            raise ValueError(f'CsvParser expected header row:\n{col_names}\nreceived:\n{self.header}')
    else:
      self.header = None

    # Define the row constructor.
    row_seq_fn:Callable[[Sequence[Any]],Any]
    if as_dicts:
      if cols is None:
        raise ValueError('CsvParser: `as_dicts` option requires `cols` argument to be provided.')
      else:
        if remap_keys:
          row_seq_fn = lambda row: { remap_keys.get(key, key) : try_cell_ctor(cell_ctor, cell, key)
            for (key, cell_ctor), cell in zip(cols.items(), row)
            if cell_ctor is not None and (preserve_empty_vals or cell) }
        else: # No remap_keys.
          row_seq_fn = lambda row: { key : try_cell_ctor(cell_ctor, cell, key)
            for (key, cell_ctor), cell in zip(cols.items(), row)
            if cell_ctor is not None and (preserve_empty_vals or cell) }
    else: # Sequence.
      if cols is None:
        row_seq_fn = lambda row: row
      else:
        len_cols = len(cols)
        def row_seq_fn(row:Sequence[Any]) -> list[Any]:
          if len(row) != len_cols:
            raise ValueError(f'CsvParser:\n  expected {len_cols} columns: {list(cols.keys())};\n'
              f'  received {len(row)} columns: {row!r}.')
          return [try_cell_ctor(cell_ctor, cell, key)
            for (key, cell_ctor), cell in zip(cols.items(), row)
            if cell_ctor is not None]

    if row_ctor is not None:
      if spread_args:
        if as_dicts:
          row_fn = lambda row: row_ctor(**row_seq_fn(row)) # type: ignore[arg-type]
        else:
          row_fn = lambda row: row_ctor(*row_seq_fn(row))
      else: # No spread_args.
        row_fn = lambda row: row_ctor(row_seq_fn(row))
    else: # No row_ctor.
      row_fn = row_seq_fn

    self.row_fn = row_fn


  def __iter__(self) -> Iterator[Any]:
    for i, row in enumerate(self._reader):
      try: yield self.row_fn(row) # type: ignore[no-untyped-call]
      except Exception as e:
        e.add_note(f'Error parsing row {i+1}: {row!r}.')
        raise


  @cached_property
  def keys(self) -> tuple[str,...]:
    remap_keys = self.remap_keys
    if self.cols is None:
      raise ValueError('CsvLoader.keys() requires `cols` constructor argument was provided.')
    return tuple(remap_keys.get(k, k) for k, v in self.cols.items() if v is not None)


def try_cell_ctor(ctor:Callable, cell:Any, col:str) -> Any:
  try: return ctor(cell)
  except Exception as e:
    e.add_note(f'Error parsing cell {cell!r} in column {col!r}.')
    raise
