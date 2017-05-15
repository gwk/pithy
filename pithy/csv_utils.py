# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import csv
from sys import stdout
from typing import cast, Any, Iterable, Iterator, Optional, Sequence, TextIO, Tuple, TypeVar, Union


T = TypeVar('T')


def load_csv(file: TextIO,
 dialect:Optional[str]=None,
 delimiter:Optional[str]=None,
 doublequote:Optional[bool]=None,
 escapechar:Optional[str]=None,
 quotechar:Optional[str]=None,
 quoting:Optional[int]=None,
 skipinitialspace:Optional[bool]=None,
 strict:Optional[bool]=None,
 header:Union[None, bool, Sequence[str]]=None) -> Iterator[Sequence[str]]:
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
  reader = cast(Iterator[Sequence], csv.reader(file, dialect, **opts)) # type: ignore
  if header is None or isinstance(header, bool):
    if header: next(reader) # simply discard.
  else: # match expected against actual.
    row = next(reader)
    if row != list(header):
      raise ValueError(f'load_csv expected header:\n{header}\nreceived:\n{row}')
  return reader


def write_csv(f: TextIO, header: Optional[Sequence[str]], rows: Iterable[Sequence]) -> None:
  w = csv.writer(f) # type: ignore # not annotated in typeshed.
  if header is not None: w.writerow(header)
  w.writerows(rows)


def out_csv(header: Optional[Sequence[str]], rows: Iterable[Sequence]) -> None:
  write_csv(f=stdout, header=header, rows=rows)
