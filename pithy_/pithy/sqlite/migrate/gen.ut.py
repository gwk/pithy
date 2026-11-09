# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import closing

from pithy.logs import adjust_log_level
from pithy.sqlite.conn import Conn
from pithy.sqlite.migrate.gen import gen_migration
from pithy.sqlite.migrate.transaction import run_migration
from pithy.sqlite.schema import Column, Index, Schema, Table
from utest import utest_run, utest_val


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
