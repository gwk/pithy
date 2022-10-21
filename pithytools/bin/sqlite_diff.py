# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser

from pithy.sqlite import Connection

def main() -> None:

  parser = ArgumentParser(description='Diff two SQLite database files.')
  parser.add_argument('path_a', help='Path to the first database file.')
  parser.add_argument('path_b', help='Path to the second database file.')

  args = parser.parse_args()
  ca = Connection(args.path_a)
  cb = Connection(args.path_b)

  a_tables = set(ca.run("SELECT name FROM sqlite_master WHERE type = 'table'").col())
  b_tables = set(cb.run("SELECT name FROM sqlite_master WHERE type = 'table'").col())
  common_tables = a_tables & b_tables

  if a_only_tables := a_tables - b_tables:
    print(f'Tables only in {args.path_a}: {a_only_tables}')

  if b_only_tables := b_tables - a_tables:
    print(f'Tables only in {args.path_b}: {b_only_tables}')

  for table in sorted(common_tables):
    diff_table(ca, cb, table)


def diff_table(ca: Connection, cb: Connection, table: str):

  a_sql = ca.run("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :table", table=table).one_col()
  b_sql = cb.run("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :table", table=table).one_col()

  first = True
  def msg(*msg:str):
    nonlocal first
    if first:
      print(f'\nTable {table}:')
      first = False
    print(*msg)

  if a_sql != b_sql:
    msg(f'table: {table}: SQL differs.')
    print(f'a:', a_sql)
    print(f'b:', b_sql)
    print()
    return

  a_ids = set(ca.run(f'SELECT rowid FROM {table}').col())
  b_ids = set(cb.run(f'SELECT rowid FROM {table}').col())

  if a_only_ids := a_ids - b_ids:
    msg(f'Rows only in {ca.path}:')
    for id in sorted(a_only_ids):
      print(ca.run(f'SELECT * FROM {table} WHERE rowid = :id', id=id).one().qdi())

  if b_only_ids := b_ids - a_ids:
    msg(f'Rows only in {cb.path}:')
    for id in sorted(b_only_ids):
      print(ca.run(f'SELECT * FROM {table} WHERE rowid = :id', id=id).one().qdi())
