# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import cast, Iterable, NoReturn

from pithy.iterable import fan_by_key_fn, joinR

from . import Connection, Cursor, Row
from .schema import Column, Index, Schema, Table, TableDepStructure
from .util import sql_quote_entity_always as sql_qe


class GenMigrationError(Exception):

  @classmethod
  def confusing_column_changes(cls, removed:Iterable[Column], added:Iterable[Column]) -> 'GenMigrationError':
    removed_str = joinR('\n    ', sorted(removed))
    added_str = joinR('\n    ', sorted(added))
    return cls(f'Confusing column changes:\n  removed:\n    {removed_str}\n  added:\n    {added_str}\n')

  def fail(self) -> NoReturn: exit(str(self))


class MigrationError(Exception): pass


class MigrationStep:

  def sql(self) -> str: raise NotImplementedError


class ReorderColumns(MigrationStep):
  pass


def gen_migration(*, schema:Schema, conn:Connection) -> list[str]:
  c = conn.cursor()
  old_table_sqls:dict[str,str] = dict(
    c.run(f"SELECT name, sql FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"))

  stmts = []
  for table in schema.tables:
    old_sql = old_table_sqls.get(table.name)
    needs_rebuild, table_stmts = gen_table_migration(new=table, old=old_sql)
    stmts.extend(table_stmts)

    old_deps:dict[str,Row] = dict((row.name, row) for row in
      c.run("SELECT type, name, sql FROM sqlite_schema WHERE type != 'table' AND tbl_name = :name AND name NOT LIKE 'sqlite_%'",
        name=table.name))

    new_deps = schema.table_deps[table.name]

    stmts.extend(gen_deps_migration(new_deps=new_deps, old_deps=old_deps, needs_rebuild=needs_rebuild))

  # TODO: handle table drops.

  return stmts


def gen_table_migration(*, new:Table, old:str|Table|None) -> tuple[bool,list[str]]:
  '''
  Generate a migration from the given SQL statement or previous table to this table.
  Returns a tuple of (needs_rebuild, stmts).
  '''

  if not old: return False, [new.sql()]

  if isinstance(old, str):
    old = Table.parse(new.name + '(old)', old)

  assert new.name == old.name
  qname = sql_qe(new.name)
  if old == new: return False, []

  matched_cols = new.match_columns_by_name(old)
  removed = [oc for oc in old.columns if oc.name not in matched_cols]
  added = [nc for nc in new.columns if nc.name not in matched_cols]

  # Be careful to distinguish between dropped and added vs renamed columns.
  # For safety, we require that a given change either only add, drop, or rename columns.

  if removed and added: # Assume this is a rename.
    if len(new.columns) != len(old.columns):
      raise GenMigrationError.confusing_column_changes(removed=removed, added=added)
    return False, gen_rename_columns(new=new, old=old, matched_cols=matched_cols)

  stmts = []
  cols = list(old.columns)

  # Drop columns.
  for col in removed:
    stmts.append(f'ALTER TABLE {qname} DROP COLUMN {sql_qe(col.name)}')
    cols.remove(col)

  # Add columns.
  for col in added:
    stmts.append(f'ALTER TABLE {qname} ADD COLUMN {col.sql()}')
    cols.append(col)

  assert set(nc.name for nc in new.columns) == set(c.name for c in cols)

  diff_hints = []
  for (nc, c) in zip(new.columns, cols):
    if dh := nc.diff_hint(c, exact_type=False):
      diff_hints.append(f'{sql_qe(nc.name)} {dh}')
      if dh.endswith('order'): break

  needs_rebuild = bool(diff_hints)
  if needs_rebuild:
    stmts.append(f'-- Rebuilding {qname} due to {", ".join(diff_hints)}.')
    stmts.extend(gen_table_rebuild(new=new, old_name=old.name, cols=cols))

  return needs_rebuild, stmts


def gen_rename_columns(*, new:Table, old:Table, matched_cols:dict[str,Column]) -> list[str]:
  assert len(new.columns) == len(old.columns)
  stmts = ['-- Renaming columns.']
  for i, (nc, oc) in enumerate(zip(new.columns, old.columns)):
    if nc.name == oc.name:
      if dh := nc.diff_hint(oc, exact_type=False):
        raise GenMigrationError(f'Rename migration failed: {nc.name!r} semantic details differ ({dh}):\n  old: {oc}\n  new: {nc}')
      continue
    is_nc_matched = nc.name in matched_cols
    is_oc_matched = oc.name in matched_cols
    if is_nc_matched != is_oc_matched:
      raise GenMigrationError(f'Rename failed due to misaligned columns at position {i}: old: {oc!r}, new: {nc!r}.')
    stmts.append(f'ALTER TABLE {sql_qe(new.name)} RENAME COLUMN {sql_qe(oc.name)} TO {sql_qe(nc.name)}')
  return stmts


def gen_table_rebuild(*, new:Table, old_name:str, cols:list[Column]) -> list[str]:

  stmts = []

  # Following the 12 steps. https://www.sqlite.org/lang_altertable.html#making_other_kinds_of_table_schema_changes

  # 3. The schema contains all indexes, triggers, and views associated with the table, so we can rebuild them.

  tmp_name = new.name + '__rebuild_in_progress'
  old_name_q = sql_qe(old_name)
  tmp_name_q = sql_qe(tmp_name)
  stmts.append(new.sql(name=tmp_name)) # 4. Create a new table with the desired schema and temporary name.
  stmts.append(f'INSERT INTO {tmp_name_q} SELECT {new.quoted_material_columns_str} FROM {old_name_q}') # 5. Copy the data.
  stmts.append(f'DROP TABLE {old_name_q}') # 6. Remove the old table.
  stmts.append(f'ALTER TABLE {tmp_name_q} RENAME TO {new.quoted_name}')

  # 8, 9. TODO: Reconstruct all indexes, triggers, and views associated with the table.

  return stmts


def gen_deps_migration(*, new_deps:tuple[TableDepStructure,...], old_deps:dict[str,Row],
 needs_rebuild:bool) -> list[str]:

  stmts = []

  new_names = set(dep.name for dep in new_deps)
  for name, dep in old_deps.items():
    if name not in new_names:
      stmts.append(f'DROP {dep.type.upper()} IF EXISTS {sql_qe(name)}')
      #^ Use IF EXISTS because the structure may have been dropped by a table rebuild.

  for new in new_deps:
    new_sql = new.sql()
    if old := old_deps.get(new.name):
      if not needs_rebuild and old.sql == new_sql: continue
      stmts.append(f'DROP {old.type.upper()} IF EXISTS {sql_qe(old.name)}')
      stmts.append(new_sql)
    else:
      stmts.append(new_sql)

  return stmts


def run_migration(conn:Connection, migration:list[str], max_errors=100, backup=True) -> None:

  if backup: conn.backup_and_print_progress()
  print('Migrating…')
  c = conn.cursor()

  try:
    for step in migration_start: c.execute(step) # Steps 1, 2.
    for step in migration: c.execute(step) # Steps 3-9.

    # Step 10. Check for foreign key errors.
    run_check(c, 'foreign_key_check', max_errors=max_errors)
  except Exception:
    c.execute('ROLLBACK')
    print('Migration failed.')
    raise
  else:
    c.execute('COMMIT') # 11.
    print('Migration complete.')
  finally:
    c.execute('PRAGMA foreign_keys = ON') # 12.


def run_check(cursor:Cursor, check:str, args:str='', max_errors=100) -> None:
  args_str = f'({args})' if args else ''
  stmt = f'PRAGMA {check}{args_str}'
  print(f'Running {stmt!r}.')
  n = 0
  for n, error in enumerate(cursor.execute(stmt), 1):
    print(f'{check} error:', *error, sep='\t')
    if n >= max_errors: break
  if n:
    s = 's' if n > 1 else ''
    plus = '+' if n >= max_errors else ''
    raise MigrationError(f'{check} failed with {n}{plus} error{s}.')


migration_start = [
  'PRAGMA foreign_keys = OFF', # 1.
  'BEGIN TRANSACTION', # 2.
]
