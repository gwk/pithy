#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from os import remove as remove_file
from os.path import exists as path_exists
from random import random
from sqlite3 import connect, Connection
from statistics import fmean, median, stdev, variance
from time import perf_counter
from typing import Iterable


path = 'time-series-avg.db'

def main() -> None:

  parser = ArgumentParser()
  parser.add_argument('-num-runs', type=int, default=16, help='Number of iterations to run the test.')
  parser.add_argument('-rows', type=int, default=1<<20, help='Number rows to insert.')
  parser.add_argument('-window', type=int, default=1<<10, help='Number of rows to average.')
  parser.add_argument('-verbose', action='store_true', help='Print extra information.')
  parser.add_argument('-leave-db', action='store_true', help='Do not delete the final database upon completion.')

  args = parser.parse_args()
  num_rows = args.rows

  ts_inc = 0.1
  ts_window = args.window * ts_inc
  ts_end = num_rows * ts_inc

  conn = connect(path, detect_types=0, isolation_level=None, check_same_thread=False)
  build_db(conn, num_rows=num_rows, ts_inc=ts_inc)

  times = [
    run_query(conn=conn, ts_window=ts_window, ts_end=ts_end, verbose=args.verbose)
    for _ in range(args.num_runs)]

  print(compute_stats(num_rows=num_rows, times=times))
  if not args.leave_db and path_exists(path): remove_file(path)


def build_db(db:Connection, num_rows:int, ts_inc:float) -> None:
  c = db.cursor()
  c.execute('PRAGMA journal_mode = WAL')
  c.execute('DROP TABLE IF EXISTS Measurement')
  c.execute('''
    CREATE TABLE Measurement (
      timestamp REAL PRIMARY KEY,
      value REAL NOT NULL
    ) WITHOUT ROWID
  ''')

  # Populate the table.
  start_time = perf_counter()
  for i in range(num_rows):
    timestamp = i * ts_inc # Increment by some fraction, to better simulate a time series.
    value = random()
    c.execute('INSERT INTO Measurement (timestamp, value) VALUES (?, ?)', (timestamp, value))
  end_time = perf_counter()
  print(f'Inserted {num_rows:,} rows in {end_time - start_time:.4f}s.')


def run_query(conn:Connection, ts_window:float, ts_end:float, verbose:bool) -> float:
  c = conn.cursor()
  tss = 0.0
  sum_avgs = 0.0
  count = 0
  start_time = perf_counter()
  while tss <= ts_end:
    tse = tss + ts_window
    c.execute('SELECT avg(value) FROM Measurement WHERE timestamp >= :tss AND timestamp < :tse', dict(tss=tss, tse=tse))
    row = c.fetchone()
    if avg := row[0]:
      sum_avgs += avg
    count += 1
    tss = tse
  end_time = perf_counter()
  dur = end_time - start_time
  if verbose:
    print(f'{count} window queries took {dur:.5f}s; avg: {sum_avgs/count:.5f}.')
  return dur


def compute_stats(num_rows:int, times:list[float]) -> str:
  n = len(times)
  mean_ = fmean(times)
  median_ = median(times)
  variance_ = variance(times) if n > 1 else 0
  stdev_ = stdev(times) if n > 1 else 0

  return f'Iterations: {n:,}  rows: {num_rows:,}  mean: {mean_:.4f};  median: {median_:.4f};  variance: { variance_:.6f};  stddev: { stdev_:.6f}.'


if __name__ == '__main__': main()
