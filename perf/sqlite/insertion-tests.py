#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from os import remove as remove_file
from os.path import exists as path_exists
from random import randbytes
from sqlite3 import connect, Row
from statistics import fmean, median, stdev, variance
from time import perf_counter
from typing import Any


path = 'insertion-tests.db'

def main() -> None:

  parser = ArgumentParser()
  parser.add_argument('-num-runs', type=int, default=16, help='Number of iterations to run the test.')
  parser.add_argument('-rows', type=int, default=1<<14, help='Number rows to insert.')
  parser.add_argument('-el-size', type=int, default=64, help='Size in bytes of each row element.')
  parser.add_argument('-verbose', action='store_true', help='Print extra information.')
  parser.add_argument('-leave-db', action='store_true', help='Do not delete the final database upon completion.')

  args = parser.parse_args()
  num_rows = args.rows

  insert_times = [
    run_insertion_test(num_rows=num_rows, el_size=args.el_size, verbose=args.verbose)
    for _ in range(args.num_runs)]

  print(compute_stats(num_rows=num_rows, times=insert_times))
  if not args.leave_db and path_exists(path): remove_file(path)


def run_insertion_test(num_rows:int, el_size:int, verbose:bool) -> None:
  if path_exists(path): remove_file(path)
  conn = connect(path, isolation_level=None)
  conn.row_factory = Row
  c = conn.cursor()

  #pragma_start = perf_counter()
  c.execute('PRAGMA journal_mode = WAL') # Test is approximately 20x slower without this.
  #print(f'PRAGMA journal_mode time: {perf_counter() - pragma_start:.5f}') # Takes approximately 0.0001s on M1 mac.

  c.execute('''
    CREATE TABLE T (
      id INTEGER PRIMARY KEY,
      b0 BLOB
    )''')

  # Populate the tables.
  print(f'Inserting {num_rows} rows…', end='')
  insert_start = perf_counter()
  for i in range(num_rows):
    b0 = randbytes(el_size)
    args:dict[str,Any] = dict(id=i, b0=b0)
    c.execute('INSERT INTO T (id, b0) VALUES (:id, :b0)', args)

  insert_dur = perf_counter() - insert_start
  print(f'Inserts took {insert_dur:.3f} seconds.')
  conn.close()
  return insert_dur


def compute_stats(num_rows:int, times:list[float]) -> str:
  n = len(times)
  mean_ = fmean(times)
  median_ = median(times)
  variance_ = variance(times) if n > 1 else 0
  stdev_ = stdev(times) if n > 1 else 0

  return f'Iterations: {n:,}  rows: {num_rows:,}  mean: {mean_:.4f};  median: {median_:.4f};  variance: { variance_:.6f};  stddev: { stdev_:.6f}.'


if __name__ == '__main__': main()
