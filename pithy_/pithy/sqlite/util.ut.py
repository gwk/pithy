# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from datetime import date as Date, datetime as DateTime, time as Time, UTC

from pithy.json import render_json
from pithy.sqlite.util import insert_values_stmt, sqlite_native_val
from utest import utest


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
