# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import csv
from sys import stdout
from typing import Any, Iterable, Iterator, Sequence, TextIO, TypeVar


T = TypeVar('T')


def write_csv(f: TextIO, header: Sequence[str], rows: Iterable[Sequence]) -> None:
  w = csv.writer(f) # type: ignore # not annotated in typeshed.
  w.writerow(header)
  w.writerows(rows)


def out_csv(header: Sequence[str], rows: Iterable[Sequence]) -> None:
  write_csv(f=stdout, header=header, rows=rows)


def drop1(reader: Iterable[T]) -> Iterator[T]:
  it = iter(reader)
  next(it)
  return it
