# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import csv
from sys import stdout
from typing import Any, Iterable, Sequence, TypeVar
# from typing.io import TextIOBase # mypy 0.46 chokes.

def write_csv(f: Any, header: Sequence[str], rows: Iterable[Sequence]) -> None:
  w = csv.writer(f)
  w.writerow(header)
  w.writerows(rows)


def out_csv(header: Sequence[str], rows: Iterable[Sequence]) -> None:
  write_csv(f=stdout, header=header, rows=rows)
