# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# TODO: handle leading UTF8-BOM.

import csv
import collections
from csv import QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONNUMERIC, QUOTE_NONE
from sys import stdout
from types import TracebackType
from typing import Any, ContextManager, Iterable, Iterator, Optional, Sequence, TextIO, Type, Union


def load_csv(file: TextIO,
 dialect:Optional[str]=None,
 delimiter:Optional[str]=None,
 doublequote:Optional[bool]=None,
 escapechar:Optional[str]=None,
 quotechar:Optional[str]=None,
 quoting:int=QUOTE_MINIMAL,
 skipinitialspace:Optional[bool]=None,
 strict:Optional[bool]=None,
 row_type:type=None,
 header:Union[None, bool, Sequence[str]]=None) -> 'CSVFileReader':

  return CSVFileReader(
    file=file,
    dialect=dialect,
    delimiter=delimiter,
    doublequote=doublequote,
    escapechar=escapechar,
    quotechar=quotechar,
    quoting=quoting,
    skipinitialspace=skipinitialspace,
    strict=strict,
    row_type=row_type,
    header=header)


def write_csv(f:TextIO, *, quoting:int=QUOTE_MINIMAL, header:Optional[Sequence[str]], rows:Iterable[Sequence]) -> None:
  w = csv.writer(f, quoting=quoting)
  if header is not None: w.writerow(header)
  w.writerows(rows)


def out_csv(*, quoting:int=QUOTE_MINIMAL, header:Optional[Sequence[str]], rows:Iterable[Sequence]) -> None:
  write_csv(f=stdout, quoting=quoting, header=header, rows=rows)


class CSVFileReader(Iterable, ContextManager):

  def __init__(self, file: TextIO,
   dialect:Optional[str]=None,
   delimiter:Optional[str]=None,
   doublequote:Optional[bool]=None,
   escapechar:Optional[str]=None,
   quotechar:Optional[str]=None,
   quoting:Optional[int]=None,
   skipinitialspace:Optional[bool]=None,
   strict:Optional[bool]=None,
   row_type:type=None,
   header:Union[None, bool, Sequence[str]]=None) -> None:

    opts = { k : v for (k, v) in [
      ('dialect', dialect),
      ('delimiter', delimiter),
      ('doublequote', doublequote),
      ('escapechar', escapechar),
      ('quotechar', quotechar),
      ('quoting', quoting),
      ('skipinitialspace', skipinitialspace),
      ('strict', strict),
      ] if v is not None }

    self._reader = csv.reader(file, dialect, **opts)
    self.file = file
    self.row_type = row_type

    if header is None or isinstance(header, bool):
      if header: next(self._reader) # simply discard.
    else: # match expected against actual.
      row = next(self._reader)
      list_header = list(header)
      if row != list_header:
        raise ValueError(f'load_csv expected header:\n{list_header}\nreceived:\n{row}')


  def __iter__(self) -> Iterator[Any]:
    if self.row_type is None:
      return self._reader
    else:
      return (self.row_type(*r) for r in self._reader)


  def __enter__(self) -> 'CSVFileReader':
    return self


  def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException],
   traceback: Optional[TracebackType]) -> None:
    self.file.close()
