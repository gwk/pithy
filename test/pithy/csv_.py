#!/usr/bin/env python3

from utest import utest_seq
from pithy.csv import write_csv, load_csv, out_csv


header = ['str', 'int', 'float']
rows = [['a', 1, 0.0], ['b', 2, 0.5]]
rows_as_strs = [[str(cell) for cell in row] for row in rows]
rows_as_dicts = [{key : cell for key, cell in zip(header, row)} for row in rows]
rows_as_strs_dicts = [{key: str(cell) for key, cell in zip(header, row)} for row in rows]

out_csv(header=header, rows=rows)

# Without header.

with open('test-no-header.csv', 'w') as f:
  write_csv(f, header=None, rows=rows)

with open('test-no-header.csv', 'r') as f:
  utest_seq(rows_as_strs, load_csv, f, has_header=False)


# With header.

with open('test.csv', 'w') as f:
  write_csv(f, header=header, rows=rows)

with open('test.csv', 'r') as f:
  utest_seq(rows_as_strs, load_csv, f)

with open('test.csv', 'r') as f:
  utest_seq(rows, load_csv, f, cols=dict(str=str, int=int, float=float))

with open('test.csv', 'r') as f:
  utest_seq(rows_as_dicts, load_csv, f, as_dicts=True, cols=dict(str=str, int=int, float=float))
