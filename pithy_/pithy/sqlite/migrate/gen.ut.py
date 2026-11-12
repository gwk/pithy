# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import closing
from typing import Any

from pithy.logs import adjust_log_level
from pithy.sqlite.conn import Conn
from pithy.sqlite.migrate.gen import find_undeclared, gen_migration, GenMigrationError
from pithy.sqlite.migrate.transaction import run_migration
from pithy.sqlite.schema import Column, Index, Schema, Table
from utest import utest, utest_exc, utest_run, utest_val


def trigger_names(conn:Conn) -> list[str]:
  return [row[0] for row in conn.execute("SELECT name FROM sqlite_schema WHERE type = 'trigger' ORDER BY name")]


@utest_run
def _test_unmanaged_trigger_is_skipped() -> None:
  'An undeclared index is dropped, but a trigger on the same table is left alone.'
  with closing(Conn(':memory:', mode='memory')) as conn, adjust_log_level('silent'): # Silences the expected trigger warning.
    conn.execute('CREATE TABLE "t" ("id" INTEGER, "n" INTEGER)')
    conn.execute('CREATE INDEX "stale_idx" ON "t" ("n")')
    conn.execute('CREATE TRIGGER "tr" AFTER INSERT ON "t" BEGIN UPDATE "t" SET "n" = 0 WHERE "id" = new."id"; END')
    schema = Schema('main', structures=[
      Table('t', columns=(Column('id', int, is_opt=True), Column('n', int, is_opt=True))),
      Index('keep_idx', table='t', columns=('id',))])

    stmts = gen_migration(conn=conn, schema=schema)
    utest_val(['DROP INDEX IF EXISTS main."stale_idx"', 'CREATE INDEX main."keep_idx"\n  ON "t" (id)'], stmts)
    run_migration(conn, stmts)
    utest_val(['tr'], trigger_names(conn))
    utest_val([], gen_migration(conn=conn, schema=schema))


@utest_run
def _test_descriptions_are_omitted() -> None:
  'Descriptions do not appear in generated statements, and changing them generates nothing.'

  def schema(desc:str) -> Schema:
    return Schema('main', desc=desc, structures=[
      Table('t', desc=desc, columns=(Column('id', int, is_opt=True, desc=desc), Column('n', int, is_opt=True, desc=desc))),
      Index('idx', table='t', columns=('id',), desc=desc)])

  with closing(Conn(':memory:', mode='memory')) as conn, adjust_log_level('silent'):
    stmts = gen_migration(conn=conn, schema=schema('Original.'))
    utest_val(['CREATE TABLE main."t" (\n  id INTEGER,\n  n INTEGER\n)', 'CREATE INDEX main."idx"\n  ON "t" (id)'], stmts)
    run_migration(conn, stmts)
    utest([], gen_migration, conn=conn, schema=schema('Original.'))
    utest([], gen_migration, conn=conn, schema=schema('Changed.'))


@utest_run
def _test_table_level_changes_rebuild() -> None:
  'Changes to strictness, rowid use and the compound primary key rebuild the table, and the result is stable.'

  def schema(**table_args:Any) -> Schema:
    return Schema('main', structures=[
      Table('t', columns=(Column('a', int), Column('b', int)), **table_args),
      Index('idx', table='t', columns=('b',))])

  variants:list[dict[str,Any]] = [
    dict(is_strict=True),
    dict(is_strict=True, primary_key=('a', 'b')),
    dict(is_strict=True, primary_key=('b', 'a')),
    dict(is_strict=True, primary_key=('b', 'a'), without_rowid=True),
    dict(),
  ]
  with closing(Conn(':memory:', mode='memory')) as conn, adjust_log_level('silent'):
    run_migration(conn, gen_migration(conn=conn, schema=schema()))
    conn.execute('INSERT INTO t VALUES (1, 2)')
    for table_args in variants:
      stmts = gen_migration(conn=conn, schema=schema(**table_args))
      utest_val(True, any(s.startswith('-- Rebuilding') for s in stmts), f'rebuild for {table_args}')
      run_migration(conn, stmts)
      utest([], gen_migration, conn=conn, schema=schema(**table_args), _utest_label=f'stable for {table_args}')
    utest_val([(1, 2)], [tuple(r) for r in conn.execute('SELECT a, b FROM t')])
    utest_val(['idx'], [r[0] for r in conn.execute("SELECT name FROM sqlite_schema WHERE type = 'index' AND name = 'idx'")])


@utest_run
def _test_renamed_primary_key_column_is_stable() -> None:
  'SQLite quotes a renamed column in the stored primary key; this does not register as a primary key change.'

  def schema(name:str) -> Schema:
    return Schema('main', structures=[Table('t', primary_key=(name, 'b'), columns=(Column(name, int), Column('b', int)))])

  with closing(Conn(':memory:', mode='memory')) as conn, adjust_log_level('silent'):
    run_migration(conn, gen_migration(conn=conn, schema=schema('a')))
    stmts = gen_migration(conn=conn, schema=schema('a2'))
    utest_val(['-- Renaming columns.', 'ALTER TABLE main."t" RENAME COLUMN "a" TO "a2"'], stmts)
    run_migration(conn, stmts)
    utest([], gen_migration, conn=conn, schema=schema('a2'))


@utest_run
def _test_rename_with_table_level_change_is_rejected() -> None:
  with closing(Conn(':memory:', mode='memory')) as conn, adjust_log_level('silent'):
    run_migration(conn, gen_migration(conn=conn, schema=Schema('main', structures=[Table('t', columns=(Column('a', int),))])))
    changed = Schema('main', structures=[Table('t', is_strict=True, columns=(Column('a2', int),))])
    utest_exc(GenMigrationError, gen_migration, conn=conn, schema=changed)

  def keyed(name:str, primary_key:tuple[str,...]) -> Schema:
    return Schema('main', structures=[Table('t', primary_key=primary_key, columns=(Column(name, int), Column('b', int)))])

  with closing(Conn(':memory:', mode='memory')) as conn, adjust_log_level('silent'):
    run_migration(conn, gen_migration(conn=conn, schema=keyed('a', ('a', 'b'))))
    utest_exc(GenMigrationError, gen_migration, conn=conn, schema=keyed('a2', ('b', 'a2')), _utest_label='key reorder')


@utest_run
def _test_find_undeclared() -> None:
  'Undeclared objects are listed for the named database only; declared, internal and shadow objects are omitted.'
  with closing(Conn(':memory:', mode='memory')) as conn:
    conn.execute("ATTACH DATABASE ':memory:' AS aux")
    conn.execute('CREATE TABLE main.keep (id INTEGER PRIMARY KEY AUTOINCREMENT, n INTEGER UNIQUE)')
    conn.execute('CREATE INDEX main.keep_idx ON keep (n)')
    conn.execute('CREATE INDEX main.keep_stale_idx ON keep (id, n)')
    conn.execute('CREATE TABLE main.removed (id INTEGER, n INTEGER UNIQUE)')
    conn.execute('CREATE INDEX main.removed_idx ON removed (n)')
    conn.execute('CREATE TRIGGER main.removed_tr AFTER INSERT ON removed BEGIN DELETE FROM keep; END')
    conn.execute('CREATE VIEW main.a_view AS SELECT id FROM keep')
    conn.execute('CREATE VIRTUAL TABLE main.search USING fts5(body)')
    conn.execute('CREATE TABLE aux.other (id INTEGER)')
    schema = Schema('main', structures=[
      Table('keep', columns=(Column('id', int, is_primary=True, is_unique=True), Column('n', int, is_opt=True, is_unique=True))),
      Index('keep_idx', table='keep', columns=('n',))])

    utest_val([
      ('view', 'a_view', 'a_view'),
      ('index', 'keep_stale_idx', 'keep'),
      ('table', 'removed', 'removed'),
      ('index', 'removed_idx', 'removed'),
      ('trigger', 'removed_tr', 'removed'),
      ('virtual', 'search', 'search'),
    ], find_undeclared(conn=conn, schema=schema))
    utest_val([('table', 'other', 'other')], find_undeclared(conn=conn, schema=Schema('aux')))
    utest_exc(GenMigrationError, find_undeclared, conn=conn, schema=Schema('missing'))
    utest_exc(GenMigrationError, gen_migration, conn=conn, schema=Schema('missing'))
