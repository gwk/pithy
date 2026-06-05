# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from contextlib import closing

from pithy.sqlite.conn import Conn
from utest import utest_exc, utest_run, utest_val


def make_conn() -> Conn:
  'Create an in-memory connection with a single-column table `t`.'
  conn = Conn(':memory:')
  conn.execute_control('CREATE TABLE t (x INT)')
  return conn


# Commit: rows inserted inside a transaction persist, and the timing is recorded.
@utest_run
def _test_commit() -> None:
  with closing(make_conn()) as conn:
    with conn:
      conn.execute_control('INSERT INTO t (x) VALUES (1)')
    utest_val(1, conn.execute('SELECT count() FROM t').one_col(), 'committed row count')
    utest_val(True, conn.transaction_time > 0, 'transaction_time recorded')


# Rollback: an exception inside the transaction undoes the insert and is annotated with timing.
@utest_run
def _test_rollback() -> None:
  with closing(make_conn()) as conn:
    class Boom(Exception): pass
    try:
      with conn:
        conn.execute_control('INSERT INTO t (x) VALUES (2)')
        raise Boom()
    except Boom as e:
      utest_val(True, hasattr(e, 'transaction_time'), 'exception annotated with transaction_time attribute')
      utest_val(True, any('transaction_time' in note for note in e.__notes__), 'exception annotated with timing note')
    utest_val(0, conn.execute('SELECT count() FROM t').one_col(), 'rolled-back row count')


# A Conn can be re-entered to run successive independent transactions.
@utest_run
def _test_successive_transactions() -> None:
  with closing(make_conn()) as conn:
    with conn:
      conn.execute_control('INSERT INTO t (x) VALUES (1)')
    with conn:
      conn.execute_control('INSERT INTO t (x) VALUES (2)')
    utest_val(2, conn.execute('SELECT count() FROM t').one_col(), 'two committed rows')


# An explicit transaction is actually open inside the block: a nested BEGIN raises.
@utest_run
def _test_transaction_is_open() -> None:
  with closing(make_conn()) as conn:
    with conn:
      utest_exc(sqlite3.OperationalError, conn.execute_control, 'BEGIN')


# contextlib.closing closes the connection on exit.
@utest_run
def _test_closing() -> None:
  conn = make_conn()
  utest_val(False, conn.closed, 'open before closing')
  with closing(conn):
    pass
  utest_val(True, conn.closed, 'closed after closing')


# execute returns an open, usable cursor; execute_control returns None.
@utest_run
def _test_cursor_lifecycle() -> None:
  with closing(make_conn()) as conn:
    with conn:
      conn.execute_control('INSERT INTO t (x) VALUES (42)')
    cursor = conn.execute('SELECT x FROM t')
    utest_val(42, cursor.one_col(), 'fetch from open cursor returned by execute')
    cursor.close()
    conn.execute_control('DELETE FROM t')
    utest_val(0, conn.execute('SELECT count() FROM t').one_col(), 'execute_control applied the statement')
