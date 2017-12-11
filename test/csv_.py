#!/usr/bin/env python3

from utest import *
from pithy.csv import *


header = ['id', 'name']
rows = [['a', '1'], ['b', '2']]

out_csv(header=header, rows=rows)

# Without header.
with open('tmp.csv', 'w') as f:
  write_csv(f, header=None, rows=rows)
with open('tmp.csv', 'r') as f:
  utest_seq(rows, load_csv, f)

# With header.
with open('tmp.csv', 'w') as f:
  write_csv(f, header=header, rows=rows)
with open('tmp.csv', 'r') as f:
  utest_seq(rows, load_csv, f, header=header)
