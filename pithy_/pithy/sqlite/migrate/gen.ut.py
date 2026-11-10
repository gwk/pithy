# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import closing

from pithy.logs import adjust_log_level
from pithy.sqlite.conn import Conn
from pithy.sqlite.migrate.gen import find_undeclared, gen_migration, GenMigrationError
from pithy.sqlite.migrate.transaction import run_migration
from pithy.sqlite.schema import Column, Index, Schema, Table
from utest import utest_exc, utest_run, utest_val


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
