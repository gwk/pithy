# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import contextmanager
from typing import Iterator

from ...logs import logE, logI
from .. import Conn, Cursor


class MigrationError(Exception): pass


@contextmanager
def migration_transaction(conn:Conn, *, max_errors:int=100) -> Iterator[Cursor]:
  '''
  Scaffolding for the 12-step migration process: https://www.sqlite.org/lang_altertable.html#making_other_kinds_of_table_schema_changes.
  Disables foreign keys (step 1), opens a single immediate transaction (step 2), yields a cursor for steps 4-9,
  runs the foreign_key_check (step 10) just before commit (step 11), and restores foreign keys (step 12).
  The PRAGMA foreign_keys toggle must occur outside any transaction, which is why it brackets the `with conn:` block.
  '''
  conn.run_effect('PRAGMA foreign_keys = OFF') # 1. TODO: query and save; only turn off if they are on.
  try:
    with conn: # 2. BEGIN IMMEDIATE; commits on success (11), rolls back if an exception propagates.
      # 3 is implicit: the schema contains all indexes, triggers, and views associated with the table, so we can rebuild them.
      c = conn.cursor()
      yield c # 4-9.
      run_migration_check(c, 'foreign_key_check', max_errors=max_errors) # 10. Check for foreign key errors.
  finally:
    conn.run_effect('PRAGMA foreign_keys = ON') # 12. TODO: only turn on if they were originally on.


def run_migration(conn:Conn, migration:list[str], max_errors:int=100) -> None:
  'Run a flat list of SQL statements as a single migration.'
  logI('Migrating.')
  try:
    with migration_transaction(conn, max_errors=max_errors) as c:
      for step in migration: c.execute(step)
  except Exception as e:
    logE('Migration failed.', exc=e)
    raise
  logI('Migration complete.')


def run_migration_check(cursor:Cursor, check:str, args:str='', max_errors:int=100) -> None:
  args_str = f'({args})' if args else ''
  stmt = f'PRAGMA {check}{args_str}'
  n = 0
  for n, error in enumerate(cursor.execute(stmt), 1):
    logE('run_migration_check error', check=check, error=error)
    if n >= max_errors: break
  if n:
    s = 's' if n > 1 else ''
    plus = '+' if n >= max_errors else ''
    logE('run_migration_check failed', stmt=stmt)
    raise MigrationError(f'{check} failed with {n}{plus} error{s}.')
