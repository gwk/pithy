# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from contextlib import closing

from pithy.sqlite.conn import _backoff_ceiling, _is_busy, Conn
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


# commit() and rollback() are unsupported in autocommit mode and raise rather than silently no-op.
@utest_run
def _test_commit_rollback_unsupported() -> None:
  with closing(make_conn()) as conn:
    utest_exc(sqlite3.ProgrammingError, conn.commit)
    utest_exc(sqlite3.ProgrammingError, conn.rollback)


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


# Re-entering a Conn that already holds a transaction raises.
@utest_run
def _test_reenter_active_transaction_raises() -> None:
  with closing(make_conn()) as conn:
    with conn:
      utest_exc(sqlite3.ProgrammingError, conn.__enter__)


# The read-only path issues a plain BEGIN and never BEGIN IMMEDIATE; the read-write path issues BEGIN IMMEDIATE.
@utest_run
def _test_ro_path_uses_plain_begin() -> None:
  with closing(make_conn()) as conn:
    statements:list[str] = []
    orig = conn.execute_control
    def record(query:str, args:object=()) -> None:
      statements.append(query)
      orig(query, args) # type: ignore[arg-type]
    conn.execute_control = record # type: ignore[method-assign]

    # Read-write path (default mode '').
    with conn: pass
    utest_val(True, 'BEGIN IMMEDIATE' in statements, 'rw path issues BEGIN IMMEDIATE')

    statements.clear()
    conn.mode = 'ro' # Force the read-only path; the in-memory db remains writable so BEGIN/COMMIT still succeed.
    with conn: pass
    utest_val(True, 'BEGIN' in statements, 'ro path issues plain BEGIN')
    utest_val(False, any('IMMEDIATE' in s for s in statements), 'ro path does not issue BEGIN IMMEDIATE')


# _is_busy matches SQLITE_BUSY (5) and SQLITE_BUSY_SNAPSHOT (517), but not other or absent error codes.
@utest_run
def _test_is_busy() -> None:
  def exc_with_code(code:int|None) -> sqlite3.OperationalError:
    e = sqlite3.OperationalError('test')
    if code is not None: e.sqlite_errorcode = code
    return e
  utest_val(True, _is_busy(exc_with_code(5)), 'SQLITE_BUSY is busy')
  utest_val(True, _is_busy(exc_with_code(517)), 'SQLITE_BUSY_SNAPSHOT is busy')
  utest_val(False, _is_busy(exc_with_code(1)), 'SQLITE_ERROR is not busy')
  utest_val(False, _is_busy(exc_with_code(6)), 'SQLITE_LOCKED is not busy')
  utest_val(False, _is_busy(exc_with_code(None)), 'no sqlite_errorcode is not busy')


# _backoff_ceiling is the deterministic per-attempt cap (jitter is applied at the call site):
# it starts at base, doubles each attempt, and plateaus at retry_max_sec.
@utest_run
def _test_backoff_ceiling() -> None:
  cap = 0.050
  base = 0.001
  def ceiling(attempt:int) -> float: return _backoff_ceiling(retry_max_sec=cap, retry_base_sec=base, attempt=attempt)
  utest_val(base, ceiling(0), 'ceiling starts at base')
  utest_val(base * 2, ceiling(1), 'ceiling doubles')
  utest_val(base * 16, ceiling(4), 'ceiling grows as base * 2**attempt below cap')
  utest_val(True, ceiling(5) > ceiling(4), 'ceiling grows while below cap')
  utest_val(cap, ceiling(10), 'ceiling plateaus at cap')
  utest_val(cap, ceiling(20), 'ceiling stays at cap')


# __exit__ commits on clean exit, rolls back on exception, and does nothing when no transaction is active.
@utest_run
def _test_exit_transaction_handling() -> None:
  # No active transaction: __exit__ is a no-op for COMMIT/ROLLBACK and does not raise.
  with closing(make_conn()) as conn:
    utest_val(False, conn.in_transaction, 'no transaction before __exit__')
    utest_val(False, conn.__exit__(None, None, None), '__exit__ returns False with no transaction')

  # Clean exit commits.
  with closing(make_conn()) as conn:
    with conn:
      conn.execute_control('INSERT INTO t (x) VALUES (1)')
    utest_val(1, conn.execute('SELECT count() FROM t').one_col(), 'clean exit committed')

  # Exception rolls back.
  with closing(make_conn()) as conn:
    class Boom(Exception): pass
    try:
      with conn:
        conn.execute_control('INSERT INTO t (x) VALUES (1)')
        raise Boom()
    except Boom: pass
    utest_val(0, conn.execute('SELECT count() FROM t').one_col(), 'exception rolled back')
