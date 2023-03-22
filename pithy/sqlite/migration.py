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


def gen_migration(*, conn:Connection, schema:Schema) -> list[str]:

  if not schema.name.isidentifier(): raise ValueError(f'Invalid schema name: {schema.name!r}')

  c = conn.cursor()
  old_table_sqls:dict[str,str] = dict(
    c.run(f"SELECT name, sql FROM {schema.name}.sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"))

  stmts = []

  for table in schema.tables:
    qname = f'{schema.name}.{sql_qe(table.name)}'

    old_sql = old_table_sqls.get(table.name)
    needs_rebuild, table_stmts = gen_table_migration(schema_name=schema.name, qname=qname, new=table, old=old_sql)
    stmts.extend(table_stmts)

    old_deps:dict[str,Row] = dict((row.name, row) for row in
      c.run(f'''
        SELECT type, name, sql FROM {schema.name}.sqlite_schema
        WHERE type != 'table' AND tbl_name = :name AND name NOT LIKE 'sqlite_%'
        ''', name=table.name))

    new_deps = schema.table_deps[table.name]

    stmts.extend(
      gen_deps_migration(schema_name=schema.name, new_deps=new_deps, old_deps=old_deps, needs_rebuild=needs_rebuild))

  # TODO: handle table drops.

  return stmts


def gen_table_migration(*, schema_name:str, qname:str, new:Table, old:str|Table|None) -> tuple[bool,list[str]]:
  '''
  Generate a migration from the given SQL statement or previous table to this table.
  Returns a tuple of (needs_rebuild, stmts).
  This represents steps 4-9 of the recommended 12 step migration process.
  '''

  if not old: return False, [new.sql(schema=schema_name)]

  if isinstance(old, str):
    old = Table.parse(new.name + '(old)', old)

  assert new.name == old.name
  if old == new: return False, []

  matched_cols = new.match_columns_by_name(old)
  removed = [oc for oc in old.columns if oc.name not in matched_cols]
  added = [nc for nc in new.columns if nc.name not in matched_cols]

  # Be careful to distinguish between dropped and added vs renamed columns.
  # For safety, we require that a given change either only add, drop, or rename columns.

  if removed and added: # Assume this is a rename.
    if len(new.columns) != len(old.columns):
      raise GenMigrationError.confusing_column_changes(removed=removed, added=added)
    return False, gen_rename_columns(qname=qname, new=new, old=old, matched_cols=matched_cols)

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
    stmts.extend(gen_table_rebuild(schema_name=schema_name, qname=qname, table=new))

  return needs_rebuild, stmts


def gen_rename_columns(*, qname:str, new:Table, old:Table, matched_cols:dict[str,Column]) -> list[str]:
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
    stmts.append(f'ALTER TABLE {qname} RENAME COLUMN {sql_qe(oc.name)} TO {sql_qe(nc.name)}')
  return stmts


def gen_table_rebuild(*, schema_name:str, qname:str, table:Table) -> list[str]:
  '''
  Steps 4-7.
  '''
  tmp_name = table.name + '__rebuild_in_progress'
  qname_tmp = f'{schema_name}.{sql_qe(tmp_name)}'
  stmts = []
  stmts.append(table.sql(schema=schema_name, name=tmp_name)) # 4. Create a new table with the desired schema and temporary name.
  stmts.append(f'INSERT INTO {qname_tmp} SELECT {table.quoted_material_columns_str} FROM {qname}') # 5. Copy the data.
  stmts.append(f'DROP TABLE {qname}') # 6. Remove the old table.
  stmts.append(f'ALTER TABLE {qname_tmp} RENAME TO {table.quoted_name}') # 7.

  return stmts


def gen_deps_migration(*, schema_name:str, new_deps:tuple[TableDepStructure,...], old_deps:dict[str,Row],
 needs_rebuild:bool) -> list[str]:
  '''
  Steps 8-9: reconstruct all indexes, triggers, and views associated with the table.
  '''

  stmts = []

  new_names = set(dep.name for dep in new_deps)
  for name, dep in old_deps.items():
    if name not in new_names:
      stmts.append(f'DROP {dep.type.upper()} IF EXISTS {schema_name}.{sql_qe(name)}')
      #^ Use IF EXISTS because the structure may have been dropped by a table rebuild.

  for new in new_deps:
    new_sql = new.sql() # Note: the sql we use for comparison has no schema name.
    if old := old_deps.get(new.name):
      if not needs_rebuild and old.sql == new_sql: continue
      stmts.append(f'DROP {old.type.upper()} IF EXISTS {schema_name}.{sql_qe(old.name)}')
      stmts.append(new_sql)
    else:
      stmts.append(new.sql(schema=schema_name)) # Note: the SQL we execute does have an explicit schema name.

  return stmts


def run_migration(conn:Connection, migration:list[str], max_errors=100, backup=True) -> None:
  '''
  12 migration steps: https://www.sqlite.org/lang_altertable.html#making_other_kinds_of_table_schema_changes
  '''

  if backup: conn.backup_and_print_progress()
  print('Migrating…')
  c = conn.cursor()

  try:
    c.execute('PRAGMA foreign_keys = OFF') # 1.
    c.execute('BEGIN TRANSACTION') # 2.
    # 3 is implicit: the schema contains all indexes, triggers, and views associated with the table, so we can rebuild them.
    for step in migration: c.execute(step) # 4-9.
    run_check(c, 'foreign_key_check', max_errors=max_errors) # 10. Check for foreign key errors.

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