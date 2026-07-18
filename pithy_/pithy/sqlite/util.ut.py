# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from datetime import date as Date, datetime as DateTime, time as Time, UTC

from pithy.frozendicts import frozendict
from pithy.json import render_json
from pithy.sqlite.util import (CURRENT_TIME, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP_Z, insert_values_stmt,
  placeholders_for_fields, sql_substitute_exprs, SqlExpr, sqlite_native_val, update_stmt)
from utest import utest, utest_exc


# Native values pass through unchanged.
utest(None, sqlite_native_val, None)
utest(True, sqlite_native_val, True)
utest(1, sqlite_native_val, 1)
utest(1.5, sqlite_native_val, 1.5)
utest('s', sqlite_native_val, 's')
utest(b'b', sqlite_native_val, b'b')

# Date, datetime and time values are converted to ISO-8601 strings,
# matching the output of the deprecated sqlite3 default adapters.
utest('2026-07-16', sqlite_native_val, Date(2026, 7, 16))
utest('2026-07-16 12:30:45', sqlite_native_val, DateTime(2026, 7, 16, 12, 30, 45))
utest('2026-07-16 12:30:45.000001', sqlite_native_val, DateTime(2026, 7, 16, 12, 30, 45, 1))
utest('2026-07-16 12:30:45+00:00', sqlite_native_val, DateTime(2026, 7, 16, 12, 30, 45, tzinfo=UTC))
utest('12:30:45', sqlite_native_val, Time(12, 30, 45))

# Other non-native values are rendered as compact JSON with sorted keys.
utest('{"a":1,"b":[2,null]}', sqlite_native_val, {'b': [2, None], 'a': 1})
utest('[1,"s"]', sqlite_native_val, [1, 's'])

# The guiding invariant: a value passed as a top-level statement argument renders identically
# to the same value embedded in a JSON document.
for val in (Date(2026, 7, 16), DateTime(2026, 7, 16, 12, 30, 45, 1), Time(12, 30, 45)):
  native = sqlite_native_val(val)
  assert isinstance(native, str)
  utest(f'["{native}"]', render_json, [val], indent=None, _utest_label=repr(val))

# The ON CONFLICT update clause uses excluded references, adding no statement parameters.
utest('INSERT OR FAIL INTO t (id, v) VALUES (:id, :v) ON CONFLICT ( id ) DO UPDATE SET v=excluded.v',
  insert_values_stmt, into='t', fields=('id', 'v'), on_conflict='id')

# SqlExpr values cannot be bound as statement arguments; they are only substituted by statement generators.
utest_exc(TypeError, sqlite_native_val, CURRENT_TIMESTAMP)

# Fields present in `exprs` get their raw SQL text substituted in place of a placeholder.
utest([':a', 'CURRENT_TIMESTAMP'], placeholders_for_fields, ('a', 'ts'), frozendict({'ts': CURRENT_TIMESTAMP}))

utest("INSERT OR FAIL INTO t (a, ts) VALUES (:a, datetime('now'))",
  insert_values_stmt, into='t', fields=('a', 'ts'), exprs=frozendict({'ts': SqlExpr("datetime('now')")}))

# The ON CONFLICT update clause references the expr field via excluded, so the expr is evaluated once in the VALUES clause.
utest('INSERT OR FAIL INTO t (id, v, ts) VALUES (:id, :v, CURRENT_TIMESTAMP)'
  ' ON CONFLICT ( id ) DO UPDATE SET v=excluded.v, ts=excluded.ts',
  insert_values_stmt, into='t', fields=('id', 'v', 'ts'), on_conflict='id',
  exprs=frozendict({'ts': CURRENT_TIMESTAMP}))

utest('UPDATE OR FAIL t SET v=:v, ts=CURRENT_TIMESTAMP WHERE id = :id',
  update_stmt, table='t', fields=('v', 'ts'), where='id = :id', exprs=frozendict({'ts': CURRENT_TIMESTAMP}))

# CURRENT_TIMESTAMP_Z appends a 'Z' suffix so the stored UTC timestamp is explicitly marked;
# the expression is parenthesized so it substitutes safely into any expression context.
utest("INSERT OR FAIL INTO t (id, ts) VALUES (:id, (CURRENT_TIMESTAMP||'Z'))",
  insert_values_stmt, into='t', fields=('id', 'ts'), exprs=frozendict({'ts': CURRENT_TIMESTAMP_Z}))

# sql_substitute_exprs replaces named placeholders with the expr SQL and returns the remaining arguments to bind.
utest(('SELECT * FROM t WHERE ts < CURRENT_TIMESTAMP AND v = :v', {'v': 1}),
  sql_substitute_exprs, 'SELECT * FROM t WHERE ts < :ts AND v = :v', {'ts': CURRENT_TIMESTAMP, 'v': 1})

# All occurrences are replaced; a longer placeholder name is not treated as a prefix match.
utest(('SELECT :ts2, CURRENT_TIME, CURRENT_TIME', {'ts2': 0}),
  sql_substitute_exprs, 'SELECT :ts2, :ts, :ts', {'ts': CURRENT_TIME, 'ts2': 0})

# Placeholders inside single-quoted string literals and double-quoted names are not substituted.
utest(('SELECT \':ts\', ":ts", CURRENT_TIMESTAMP', {}),
  sql_substitute_exprs, 'SELECT \':ts\', ":ts", :ts', {'ts': CURRENT_TIMESTAMP})

# A doubled quote is an escape and does not terminate the literal.
utest(("SELECT 'it''s :ts', CURRENT_TIME", {}),
  sql_substitute_exprs, "SELECT 'it''s :ts', :ts", {'ts': CURRENT_TIME})

# Placeholders inside comments are not substituted; a block comment may span lines or be unterminated.
utest(('SELECT CURRENT_TIME -- not :ts', {}),
  sql_substitute_exprs, 'SELECT :ts -- not :ts', {'ts': CURRENT_TIME})
utest(('SELECT /* not :ts\n or :ts */ CURRENT_TIME', {}),
  sql_substitute_exprs, 'SELECT /* not :ts\n or :ts */ :ts', {'ts': CURRENT_TIME})
utest(('SELECT CURRENT_TIME /* not :ts', {}),
  sql_substitute_exprs, 'SELECT :ts /* not :ts', {'ts': CURRENT_TIME})

# A SqlExpr argument with no matching placeholder raises, including when the only occurrence is inside a literal.
utest_exc(ValueError, sql_substitute_exprs, 'SELECT 1', {'ts': CURRENT_TIME})
utest_exc(ValueError, sql_substitute_exprs, "SELECT ':ts'", {'ts': CURRENT_TIME})
