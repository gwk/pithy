# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import csv
from typing import Iterable, Sequence, TypeVar


def write_csv(f: Iterable[str], header: Sequence[str], rows: Iterable[Sequence]):
  w = csv.writer(f)
  w.writerow(header)
  w.writerows(rows)

