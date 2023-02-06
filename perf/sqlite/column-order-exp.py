#!/usr/bin/env python3


from argparse import ArgumentParser
from random import randbytes, randint
from sqlite3 import Cursor, Row, connect
from statistics import fmean, median, stdev, variance
from time import perf_counter
from typing import Iterable


def main() -> None:
  parser = ArgumentParser()
  parser.add_argument('-num-runs', type=int, required=True, help='Number rounds to test the query.')
  parser.add_argument('-clean', action='store_true', help='Regenerate row data.')
  parser.add_argument('-print-all-times', action='store_true', help='Print all times for each query.')

  conn = connect('column-order-exp.db', isolation_level=None)
  conn.row_factory = Row
  c = conn.cursor()

  cmd_args = parser.parse_args()

  num_rows = 1<<14
  max_byte_pairs = 1<<8

  if cmd_args.clean:
    c.execute('DROP TABLE IF EXISTS Front')
    c.execute('DROP TABLE IF EXISTS Back')

    # Create two tables, with an integer column in either the front or the back,
    # and ten columns of random text.
    c.execute('''
    CREATE TABLE IF NOT EXISTS TF (
    id INTEGER PRIMARY KEY,
    n0 INTEGER,
    t0 TEXT,
    t1 TEXT,
    t2 TEXT,
    t3 TEXT,
    t4 TEXT,
    t5 TEXT,
    t6 TEXT,
    t7 TEXT,
    t8 TEXT,
    t9 TEXT)''')


    c.execute('''
    CREATE TABLE IF NOT EXISTS TB (
    id INTEGER PRIMARY KEY,
    t0 TEXT,
    t1 TEXT,
    t2 TEXT,
    t3 TEXT,
    t4 TEXT,
    t5 TEXT,
    t6 TEXT,
    t7 TEXT,
    t8 TEXT,
    t9 TEXT,
    n0 INTEGER)''')

    # Populate the tables.

    print(f'Inserting {num_rows} rows...')
    insert_start = perf_counter()
    for i in range(num_rows):
      # Insert the exact same data into each table.
      n0 = randint(0, 8)
      args:dict[str,int|str] = { f't{i}' : randbytes(randint(0, max_byte_pairs)).hex() for i in range(10) }
      args['n0'] = n0

      c.execute('''
      INSERT INTO TF (n0, t0, t1, t2, t3, t4, t5, t6, t7, t8, t9)
      VALUES (:n0, :t0, :t1, :t2, :t3, :t4, :t5, :t6, :t7, :t8, :t9)''', args)

      c.execute('''
      INSERT INTO TB (t0, t1, t2, t3, t4, t5, t6, t7, t8, t9, n0)
      VALUES (:t0, :t1, :t2, :t3, :t4, :t5, :t6, :t7, :t8, :t9, :n0)''', args)

    insert_dur = perf_counter() - insert_start
    print(f'Inserts took {insert_dur:.3f} seconds.')

  print('TF rows:', c.execute('SELECT COUNT(1) FROM TF').fetchone()[0])
  print('TB rows:', c.execute('SELECT COUNT(1) FROM TB').fetchone()[0])

  print('First TF row: ', tuple(c.execute('SELECT * FROM TF LIMIT 1').fetchone()))
  print('First TB row: ', tuple(c.execute('SELECT * FROM TB LIMIT 1').fetchone()))

  print('\nExplain TF:', *[tuple(r) for r in c.execute('EXPLAIN SELECT count(1) FROM TF WHERE n0 = 0')], sep='\n  ')
  print('\nExplain TB:', *[tuple(r) for r in c.execute('EXPLAIN SELECT count(1) FROM TB WHERE n0 = 0')], sep='\n  ')

  # Warm up the cache.
  for _ in range(2):
    query_f(c)
    query_b(c)

  # Run the queries.
  num_runs = cmd_args.num_runs
  print(f'\nRunning {num_runs} queries...')

  query_f_times = []
  query_b_times = []
  test_start = perf_counter()
  for _ in range(num_runs):
    # Alternate queries in an attempt to distribute system slowdowns and cache effects more fairly.
    query_f_times.append(query_f(c))
    query_b_times.append(query_b(c))
  test_dur = perf_counter() - test_start
  print(f'Test queries took {test_dur:.3f} seconds.')

  mean_f = fmean(query_f_times)
  mean_b = fmean(query_b_times)

  median_f = median(query_f_times)
  median_b = median(query_b_times)

  variance_f = variance(query_f_times)
  variance_b = variance(query_b_times)

  stdev_f = stdev(query_f_times)
  stdev_b = stdev(query_b_times)

  if cmd_args.print_all_times:
    print('F times:', joinCSF('{:.4f}', query_f_times))
    print('B times:', joinCSF('{:.4f}', query_b_times))

  print(f'query_f: mean: {mean_f:.4f};  median: {median_f:.4f};  variance: { variance_f:.4f};  stddev: { stdev_f:.4f}')
  print(f'query_b: mean: {mean_b:.4f};  median: {median_b:.4f};  variance: { variance_b:.4f};  stddev: { stdev_b:.4f}')

  print(f'Query for back column takes {mean_b/mean_f} as long.')

def query_f(c:Cursor) -> float:
  start = perf_counter()
  n = c.execute('SELECT count(1) FROM TF WHERE n0 = 0').fetchone()[0]
  dur = perf_counter() - start
  #print(f'query_f counted {n} rows in {dur:.3f} seconds.')
  return dur

def query_b(c:Cursor) -> float:
  start = perf_counter()
  n = c.execute('SELECT count(1) FROM TB WHERE n0 = 0').fetchone()[0]
  dur = perf_counter() - start
  #print(f'query_b counted {n} rows in {dur:.3f} seconds.')
  return dur


def joinCSF(fmt:str, iterable:Iterable) -> str:
  return ', '.join(fmt.format(el) for el in iterable)



if __name__ == '__main__': main()