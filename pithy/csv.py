# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# TODO: handle leading UTF8-BOM.

import csv
from csv import Dialect, QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC
from sys import stdout
from typing import Any, Callable, ContextManager, Iterable, Iterator, Optional, Sequence, TextIO, Type, Union

from .transtruct import bool_for_val
from .typing import OptBaseExc, OptTraceback, OptTypeBaseExc


def write_csv(f:TextIO, *, quoting:int=QUOTE_MINIMAL, header:Optional[Sequence[str]], rows:Iterable[Sequence]) -> None:
  w = csv.writer(f, quoting=quoting)
  if header is not None: w.writerow(header)
  w.writerows(rows)


def out_csv(*, quoting:int=QUOTE_MINIMAL, header:Optional[Sequence[str]], rows:Iterable[Sequence]) -> None:
  write_csv(f=stdout, quoting=quoting, header=header, rows=rows)


def load_csv(file: TextIO, *,
 dialect:Union[str,Dialect,Type[Dialect]]='excel',
 delimiter:str|None=None,
 doublequote:bool|None=None,
 escapechar:str|None=None,
 quotechar:str|None=None,
 quoting:int=QUOTE_MINIMAL,
 skipinitialspace:bool|None=None,
 strict:bool=True,
 has_header=True,
 row_ctor:Callable|None=None,
 spread_args:bool=False,
 as_dicts:bool=False,
 preserve_empty_vals:bool=False,
 cols:dict[str,Optional[Callable]]|None=None) -> 'CsvLoader':

  return CsvLoader(
    file=file,
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


'''
    assert keys is not None or header is not None and not isinstance(header, bool)
    if keys is not None:
      row_keys = keys
    else:
      row_keys = header

    row_ctor = lambda row: { key : col for key, col in zip(row_keys, row) if key is not None }
'''


class CsvLoader(Iterable, ContextManager):

  def __init__(self, file: TextIO, *,
   dialect:Union[str,Dialect,Type[Dialect]]='excel',
   delimiter:str|None=None,
   doublequote:bool|None=None,
   escapechar:str|None=None,
   quotechar:str|None=None,
   quoting:int|None=None,
   skipinitialspace:bool|None=None,
   strict:bool|None=None,
   has_header=True,
   row_ctor:Callable|None=None,
   spread_args:bool=False,
   as_dicts:bool=False,
   preserve_empty_vals:bool=False,
   cols:dict[str,Optional[Callable]]|None=None) -> None:

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

    if isinstance(file, str):
      raise ValueError('file must be an iterable of strings, not a string.')

    self._reader = csv.reader(file, dialect, **opts)
    self.file = file
    self.row_ctor = row_ctor
    self.cols = cols

    if has_header:
      try: self.header:Optional[list[str]] = [str(raw_cell) for raw_cell in next(self._reader)]
      except StopIteration: self.header = None # Allow empty files.
      else:
        if cols is not None: # Match expected header against actual.
          col_names = list(cols)
          if self.header != col_names:
            raise ValueError(f'load_csv expected header row:\n{col_names}\nreceived:\n{self.header}')
    else:
      self.header = None

    # Define the row constructor.
    row_seq_fn:Callable[[Sequence[Any]],Any]
    if as_dicts:
      if cols is None:
        raise ValueError('load_csv: as_dicts option requires cols argument to be provided.')
      else:
        row_seq_fn = lambda row: { key : cell_ctor(cell) for (key, cell_ctor), cell in zip(cols.items(), row) # type: ignore[union-attr]
          if cell_ctor is not None and (preserve_empty_vals or cell) }
    else: # Sequence.
      if cols is None:
        row_seq_fn = lambda row: row
      else:
        row_seq_fn = lambda row: [cell_ctor(cell) for cell_ctor, cell in zip(cols.values(), row) # type: ignore[union-attr]
          if cell_ctor is not None]

    if row_ctor is not None:
      if spread_args:
        if as_dicts:
          row_fn = lambda row: row_ctor(**row_seq_fn(row)) # type: ignore[arg-type]
        else:
          row_fn = lambda row: row_ctor(*row_seq_fn(row)) # type: ignore[misc]
      else:
        row_fn = lambda row: row_ctor(row_seq_fn(row)) # type: ignore[misc]
    else:
      row_fn = row_seq_fn

    self.row_fn = row_fn


  def __iter__(self) -> Iterator[Any]:
    return (self.row_fn(row) for row in self._reader) # type: ignore[no-untyped-call]


  def __enter__(self) -> 'CsvLoader':
    return self


  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> None:
    self.file.close()
