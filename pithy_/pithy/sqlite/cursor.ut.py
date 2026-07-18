# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from contextlib import closing
from datetime import date as Date, datetime as DateTime, time as Time

from pithy.sqlite import forbid_default_adapters_and_converters
from pithy.sqlite.conn import Conn
from utest import utest_exc, utest_run, utest_seq, utest_val


forbid_default_adapters_and_converters()
#^ Installed before all tests, so that the pithy.sqlite tests below also prove that
#^ argument conversion does not rely on the deprecated sqlite3 default adapters.


def make_conn() -> Conn:
  'Create an in-memory connection with a single-column table `t`.'
  conn = Conn(':memory:', mode='memory')
  conn.run_effect('CREATE TABLE t (v TEXT)')
  return conn


# Raw sqlite3 usage that relies on the deprecated default adapters now raises.
@utest_run
def _test_forbidden_default_adapters() -> None:
  with closing(sqlite3.connect(':memory:')) as raw:
    utest_exc(TypeError, raw.execute, 'SELECT ?', (Date(2026, 7, 16),))
    utest_exc(TypeError, raw.execute, 'SELECT ?', (DateTime(2026, 7, 16, 12, 30, 45),))


# Raw sqlite3 usage that relies on the deprecated default converters now raises.
@utest_run
def _test_forbidden_default_converters() -> None:
  with closing(sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES)) as raw:
    raw.execute('CREATE TABLE t (d date)')
    raw.execute("INSERT INTO t (d) VALUES ('2026-07-16')")
    cursor = raw.execute('SELECT d FROM t')
    utest_exc(TypeError, cursor.fetchone)


# execute converts positional arguments and does not mutate the caller's containers.
@utest_run
def _test_execute_positional_conversion() -> None:
  with closing(make_conn()) as conn:
    args = [DateTime(2026, 7, 16, 12, 30, 45)]
    conn.execute('INSERT INTO t (v) VALUES (?)', args).close()
    utest_val([DateTime(2026, 7, 16, 12, 30, 45)], args, 'caller args list is not mutated')
    utest_val('2026-07-16 12:30:45', conn.execute('SELECT v FROM t').one_col(), 'datetime stored as ISO text')


# execute converts named arguments and does not mutate the caller's dict.
@utest_run
def _test_execute_named_conversion() -> None:
  with closing(make_conn()) as conn:
    args = {'v': Date(2026, 7, 16)}
    conn.execute('INSERT INTO t (v) VALUES (:v)', args).close()
    utest_val({'v': Date(2026, 7, 16)}, args, 'caller args dict is not mutated')
    utest_val('2026-07-16', conn.execute('SELECT v FROM t').one_col(), 'date stored as ISO text')


# executemany converts each argument set.
@utest_run
def _test_executemany_conversion() -> None:
  with closing(make_conn()) as conn:
    conn.executemany('INSERT INTO t (v) VALUES (?)', [(Date(2026, 1, 1),), (Time(12, 30, 45),)]).close()
    utest_seq(['12:30:45', '2026-01-01'], conn.execute('SELECT v FROM t ORDER BY v').col)


# run converts keyword argument values; non-native, non-date values are rendered as JSON.
@utest_run
def _test_run_conversion() -> None:
  with closing(make_conn()) as conn:
    conn.run_effect('INSERT INTO t (v) VALUES (:v)', v={'b': 2, 'a': 1})
    utest_val('{"a":1,"b":2}', conn.execute('SELECT v FROM t').one_col(), 'dict stored as JSON text')


# insert, insert_dict and insert_seq all convert values identically.
@utest_run
def _test_insert_conversions() -> None:
  with closing(make_conn()) as conn:
    with closing(conn.cursor()) as cursor:
      cursor.insert(into='t', v=DateTime(2026, 7, 16, 12, 30, 45))
      cursor.insert_dict(into='t', args={'v': Date(2026, 7, 16)})
      cursor.insert_seq(into='t', fields=('v',), seq=[Time(12, 30, 45)])
    utest_seq(['12:30:45', '2026-07-16', '2026-07-16 12:30:45'], conn.execute('SELECT v FROM t ORDER BY v').col)


# insert and insert_dict support on_conflict upserts; the positional form previously emitted unbound placeholders.
@utest_run
def _test_insert_on_conflict() -> None:
  with closing(Conn(':memory:', mode='memory')) as conn:
    conn.run_effect('CREATE TABLE r (id INTEGER PRIMARY KEY, v TEXT)')
    with closing(conn.cursor()) as cursor:
      cursor.insert(into='r', id=1, v='a')
      cursor.insert(into='r', on_conflict='id', id=1, v='b')
      cursor.insert_dict(into='r', on_conflict='id', args={'id': 1, 'v': 'c'})
    utest_seq([(1, 'c')], lambda: (tuple(row) for row in conn.execute('SELECT id, v FROM r')))
