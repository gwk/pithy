# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

_context_keywords_ = ['alter table', 'column rename', 'database', 'ddl', 'migration generation', 'schema diff', 'table rebuild']

from typing import Iterable, Self

from ...iterable import joinR
from ...logs import logW
from ...parse import ParseError
from .. import Conn, Cursor, Row
from ..schema import Column, Schema, Table, TableDepStructure
from ..util import sql_quote_entity as qe, sql_quote_entity_always as qea, sql_quote_qual_entity as qqe
from .transaction import MigrationError


class GenMigrationError(MigrationError):
  'An expected failure to generate a migration, caused by the schemas or the database state.'

  @classmethod
  def confusing_column_changes(cls, *, table_name:str, removed:Iterable[Column], added:Iterable[Column]) -> Self:
    removed_str = joinR('\n    ', sorted(removed))
    added_str = joinR('\n    ', sorted(added))
    return cls(f'Confusing column changes for table {table_name}:\n  removed:\n    {removed_str}\n  added:\n    {added_str}\n')


def gen_migration(*, conn:Conn, schema:Schema) -> list[str]:
  '''
  Generate the statements that migrate the attached database to the declared schema.

  Descriptions are omitted from the generated statements; see `Structure.sql`.
  Description changes therefore never produce a migration.
  '''

  if not schema.name.isidentifier(): raise ValueError(f'Invalid schema name: {schema.name!r}')

  c = conn.cursor()
  check_schema_attached(c, schema.name)

  old_table_sqls:dict[str,str] = dict(
    c.run(f"SELECT name, sql FROM {schema.name}.sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"))

  stmts = []

  for table in schema.tables:
    assert isinstance(table, Table), table
    qname = f'{schema.name}.{qea(table.name)}'

    try:
      old_sql = old_table_sqls.get(table.name)
      needs_rebuild, table_stmts = gen_table_migration(schema_name=schema.name, qname=qname, new=table, old=old_sql)
      stmts.extend(table_stmts)

      old_deps = dict((row.name, row) for row in
        c.run(f'''
          SELECT type, name, sql FROM {schema.name}.sqlite_schema
          WHERE type != 'table' AND tbl_name = :name AND name NOT LIKE 'sqlite_%'
          ''', name=table.name))

      new_deps = schema.table_deps[table.name]

      stmts.extend(
        gen_deps_migration(schema_name=schema.name, new_deps=new_deps, old_deps=old_deps, needs_rebuild=needs_rebuild))
      #^ Dependents are emitted per table, interleaved with the table changes. This is sound for indexes,
      # which reference only their own table. Triggers and views can reference other tables,
      # and SQLite rejects some ALTER TABLE statements while any trigger or view has an unresolved reference.
      # Supporting them requires two phases: drop stale dependents before all table changes, and create new ones afterwards.

    except Exception as e:
      e.add_note(f'Failed to generate migration for table {qname}.')
      raise

  # TODO: handle table drops.

  return stmts


def find_undeclared(*, conn:Conn, schema:Schema) -> list[tuple[str,str,str]]:
  '''
  List the objects in the attached database that the schema does not declare, as (type, name, table) tuples.

  The type is 'table', 'virtual', 'view', 'index' or 'trigger'. The table is the object that an index or trigger belongs to;
  for the other types it equals the name. Each undeclared table is followed by its undeclared indexes and triggers.
  SQLite internal objects and the shadow tables of virtual tables are omitted, because SQLite manages them itself.
  This function only reads the database.
  '''
  if not schema.name.isidentifier(): raise ValueError(f'Invalid schema name: {schema.name!r}')

  c = conn.cursor()
  check_schema_attached(c, schema.name)

  table_types:dict[str,str] = dict(c.run('SELECT name, type FROM pragma_table_list WHERE schema = :name', name=schema.name))
  #^ Distinguishes plain tables from virtual and shadow tables; sqlite_schema reports all three as 'table'.

  declared = schema.structures_dict
  undeclared = []
  for type_, name, table in c.run(f'SELECT type, name, tbl_name FROM {schema.name}.sqlite_schema'):
    if name in declared: continue
    if name.lower().startswith('sqlite_'): continue # Internal; SQLite reserves this prefix.
    if table_types.get(table) == 'shadow': continue
    undeclared.append((table_types.get(name, type_), name, table))

  return sorted(undeclared, key=lambda el: (el[2], el[1] != el[2], el[1]))


def check_schema_attached(c:Cursor, schema_name:str) -> None:
  'Raise GenMigrationError if the connection has no database attached under schema_name.'
  if not c.run('SELECT count() FROM pragma_database_list WHERE name = :name', name=schema_name).one_col():
    raise GenMigrationError(f'Schema {schema_name!r} does not exist; was it attached?')


def gen_table_migration(*, schema_name:str, qname:str, new:Table, old:str|Table|None) -> tuple[bool,list[str]]:
  '''
  Generate a migration from the given SQL statement or previous table to this table.
  Returns a tuple of (needs_rebuild, stmts).
  This represents steps 4-9 of the recommended 12 step migration process.
  '''

  if not old: return False, [new.sql(schema=schema_name, comments=False)]

  if isinstance(old, str):
    try: old = Table.parse(new.name + '(old)', text=old)
    except ParseError as e: raise GenMigrationError(str(e)) from e


  assert new.name == old.name
  if old == new: return False, []

  matched_cols = new.match_columns_by_name(old)
  removed = [oc for oc in old.columns if oc.name not in matched_cols]
  added = [nc for nc in new.columns if nc.name not in matched_cols]

  # Be careful to distinguish between dropped and added vs renamed columns.
  # For safety, we require that a given change either only add, drop, or rename columns.

  if removed and added: # Assume this is a rename.
    if len(new.columns) != len(old.columns):
      raise GenMigrationError.confusing_column_changes(table_name=qqe(schema_name, new.name), removed=removed, added=added)
    renames = {oc.name: nc.name for oc, nc in zip(old.columns, new.columns)}
    if table_reasons := table_rebuild_reasons(new=new, old=old, renames=renames):
      raise GenMigrationError(f'Table {qqe(schema_name, new.name)} renames columns and also changes {", ".join(table_reasons)};'
        ' separate these into two migration steps.')
    return False, gen_rename_columns(qname=qname, new=new, old=old, matched_cols=matched_cols)

  stmts = []
  rebuild_reasons = []
  cols = list(old.columns)

  # Drop columns.
  for col in sorted(removed, key=lambda c: not c.virtual): # Drop virtual columns first in case of dependency.
    stmts.append(f'-- Dropping column {qea(col.name)}.')
    stmts.append(f'ALTER TABLE {qname} DROP COLUMN {qea(col.name)}')
    cols.remove(col)

  # Add columns.
  for col in sorted(added, key=lambda c: bool(c.virtual)): # Add virtual columns last in case of dependency.
    stmts.append(f'-- Adding column {qea(col.name)}.')
    stmts.append(f'ALTER TABLE {qname} ADD COLUMN {col.sql()}')
    if not col.is_opt and col.default is None:
      rebuild_reasons.append(f'Added column {qea(col.name)} is not optional and has no default value.')
    cols.append(col)

  assert set(nc.name for nc in new.columns) == set(c.name for c in cols)

  for (nc, c) in zip(new.columns, cols):
    if dh := nc.diff_hint(c, include_name=True, exact_type=False):
      rebuild_reasons.append(f'{qea(nc.name)} {dh}')
      if dh.endswith('order'): break

  rebuild_reasons.extend(table_rebuild_reasons(new=new, old=old))

  needs_rebuild = bool(rebuild_reasons)
  if needs_rebuild:
    stmts.append(f'-- Rebuilding {qname} due to {", ".join(rebuild_reasons)}.')
    stmts.extend(gen_table_rebuild(schema_name=schema_name, qname=qname, new=new, old=old))

  return needs_rebuild, stmts


def table_rebuild_reasons(*, new:Table, old:Table, renames:dict[str,str]|None=None) -> list[str]:
  '''
  Name the table-level attributes that differ. SQLite cannot alter these, so any difference requires a rebuild.

  `renames` maps old column names to new ones, so that renaming a primary key column does not register as a key change.
  '''
  renames = renames or {}
  reasons = []
  if new.is_strict != old.is_strict: reasons.append('is_strict')
  if new.without_rowid != old.without_rowid: reasons.append('without_rowid')
  if new.primary_key != tuple(renames.get(n, n) for n in old.primary_key): reasons.append('primary_key')
  return reasons


def gen_rename_columns(*, qname:str, new:Table, old:Table, matched_cols:dict[str,Column]) -> list[str]:
  assert len(new.columns) == len(old.columns)
  stmts = ['-- Renaming columns.']
  for i, (nc, oc) in enumerate(zip(new.columns, old.columns)):
    if nc.name == oc.name:
      if dh := nc.diff_hint(oc, include_name=True, exact_type=False):
        raise GenMigrationError(f'Rename migration failed: {nc.name!r} semantic details differ ({dh}):\n  old: {oc}\n  new: {nc}')
      continue
    is_nc_matched = nc.name in matched_cols
    is_oc_matched = oc.name in matched_cols
    if is_nc_matched != is_oc_matched:
      raise GenMigrationError(f'Rename failed due to misaligned columns at position {i}: old: {oc!r}, new: {nc!r}.')
    stmts.append(f'ALTER TABLE {qname} RENAME COLUMN {qea(oc.name)} TO {qea(nc.name)}')
  return stmts


def gen_table_rebuild(*, schema_name:str, qname:str, new:Table, old:Table) -> list[str]:
  '''
  Steps 4-7.
  '''
  tmp_name = new.name + '__rebuild_in_progress'
  qname_tmp = f'{schema_name}.{qea(tmp_name)}'

  selected_column_exprs = []
  for col_name in new.material_column_names:
    new_col = new.columns_dict[col_name]
    old_col = old.columns_dict.get(col_name)
    if old_col is not None and old_col.is_opt and not new_col.is_opt and new_col.default is not None:
      default_expr = new_col.default_rendered
      col_expr = f'COALESCE({qe(col_name)}, {default_expr})'
    else:
      col_expr = qe(col_name)
    selected_column_exprs.append(col_expr)

  selected_columns_str = ', '.join(selected_column_exprs)

  stmts = []
  # 4. Create a new table with the desired schema and temporary name.
  stmts.append(new.sql(schema=schema_name, name=tmp_name, comments=False))
  stmts.append(f'INSERT INTO {qname_tmp} SELECT {selected_columns_str} FROM {qname}') # 5. Copy the data.
  stmts.append(f'DROP TABLE {qname}') # 6. Remove the old table.
  stmts.append(f'ALTER TABLE {qname_tmp} RENAME TO {new.quoted_name}') # 7.

  return stmts


def gen_deps_migration(*, schema_name:str, new_deps:tuple[TableDepStructure,...], old_deps:dict[str,Row],
 needs_rebuild:bool) -> list[str]:
  '''
  Steps 8-9: reconstruct all indexes, triggers, and views associated with the table.
  '''

  stmts = []

  # Schema cannot declare triggers yet, so every existing trigger is undeclared and says nothing about developer intent.
  # Report and skip them; never generate a drop.
  # A table rebuild still drops the table's triggers implicitly, and we cannot recreate them;
  # that case is reported separately.
  triggers = sorted(name for name, dep in old_deps.items() if dep.type == 'trigger')
  for name in triggers:
    if needs_rebuild:
      logW('Table rebuild will drop an unmanaged trigger; recreate it by hand in the migration.', trigger=name,
        schema=schema_name)
    else:
      logW('Skipping unmanaged trigger; schemas do not support triggers yet.', trigger=name, schema=schema_name)
  old_deps = {name: dep for name, dep in old_deps.items() if dep.type != 'trigger'}

  new_names = set(dep.name for dep in new_deps)
  for name, dep in old_deps.items():
    if name not in new_names:
      stmts.append(f'DROP {dep.type.upper()} IF EXISTS {schema_name}.{qea(name)}')
      #^ Use IF EXISTS because the structure may have been dropped by a table rebuild.

  for new in new_deps:
    new_sql = new.sql(comments=False) # Note: the sql we use for comparison has no schema name.
    if old := old_deps.get(new.name):
      if not needs_rebuild and old.sql == new_sql: continue
      #^ This comparison requires that the rendered SQL exactly match the text stored in sqlite_schema.
      # That holds for indexes. Trigger bodies are free-form SQL, so trigger support needs a rendering that round-trips exactly;
      # otherwise every generation will drop and recreate each trigger.
      stmts.append(f'DROP {old.type.upper()} IF EXISTS {schema_name}.{qea(old.name)}')
    stmts.append(new.sql(schema=schema_name, comments=False)) # Note: the SQL we execute does have an explicit schema name.

  return stmts
