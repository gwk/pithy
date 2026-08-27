# Pithy SQLite

Use `pithy.sqlite.Conn` and `pithy.sqlite.Cursor` instead of the standard `sqlite3` connection and cursor classes.
They provide typed rows, value conversion, query helpers, timing and error context, and explicit transaction behavior.
Review their interfaces before writing database code instead of assuming the standard library behavior.

## Transactions and connection lifetime

`Conn` always uses `autocommit=True`.
Each statement outside an explicit transaction is committed independently.
`Conn.commit()` and `Conn.rollback()` are intentionally unsupported because those methods are ineffective in this mode.

Use `with conn:` to run an explicit transaction.
On enter, the context issues deferred `BEGIN` for read-only connections and `BEGIN IMMEDIATE` for a read-write connection.
The read-write case also handles retry handling for the `SQLITE_BUSY` error family.
On exit, the context commits on success or rolls back when an exception propagates.

The transaction context does not close the connection, and the same connection can run successive transaction contexts.
Use `with conn.closing():` to guarantee that a connection is closed.
Nest `with conn:` inside the closing context when both behaviors are required:

```python
with Conn(path, mode='rw').closing() as conn:
  with conn:
    conn.run_effect('UPDATE Thing SET state = :state WHERE id = :id', state=state, id=id)
```

## Database groups

`Database` represents as a set of related/attached sqlite database files, with an advisory lock for shared/exclusive file ops.
It has its own context-manager semantics to control the lifetime of the complete database-group handle.
Entering takes the advisory lock, but does not itself define a transaction.
Exiting closes the connection and releases the lock.

`DbConfig` describes SQLite files managed as one group.
The first name must be `main`; `Database` opens that file and attaches the remaining named databases to the same connection.
It verifies that every file exists, checks that the databases use WAL mode, compares their `user_version` values, configures the cache and synchronous mode, and enables `query_only` for read-only handles.
`Database.initialize()` creates missing files, enables WAL mode, and writes the group manifest.
The manifest lets generic Pithy tools discover and relocate the group without importing the entire owning application.

A normal `Database.ro()` or `Database.rw()` handle holds a shared advisory lock for its lifetime.
Shared handles may coexist; SQLite transaction locking still coordinates normal readers and writers.
Offline operations that manipulate database files directly must take the exclusive advisory lock.
Examples include restoring or replacing files and cleanup that must exclude open database handles.
The advisory lock covers the configured active database files as a group; it is not a replacement for SQLite transactions.

Use the `Database` backup and sync methods, or the `pithy.sqlite.backup` layer built on them, rather than copying live database files.
Backup restoration and other file replacement must occur under the exclusive group lock.

## Schema conventions

* Use `id` as the primary-key column name for ordinary rowid tables.
* Prefer `INTEGER PRIMARY KEY` for an ordinary rowid table.
* Use `WITHOUT ROWID` judiciously when the natural primary key is non-integer or composite. An association table whose primary key is `(thing1_id, thing2_id)` is a common case.
* Prefer `NOT NULL`. Use `0`, `''`, or another explicit sentinel when the domain gives it a clear, unambiguous meaning. Use `NULL` only when absence is materially distinct and callers are prepared to handle SQL three-valued logic.
* Name foreign-key columns `<referenced-entity>_id` unless an imported schema requires another name.
* Express uniqueness and other invariants in the schema rather than relying only on application code.
* Add indexes for established lookup, join, and ordering patterns. Do not add an index already covered by a primary-key or unique index prefix.
* Use `STRICT` tables for application-owned schemas. Depart from `STRICT` only for a concrete compatibility requirement, such as faithfully preserving a vendor API mirror.

## Dates and timestamps

* Name timestamp columns for their event using an `_at` suffix, such as `created_at`, `updated_at`, or `changed_at`.
* Store UTC timestamp strings with an explicit `Z` suffix.
* Use `CURRENT_TIMESTAMP_Z` when SQLite should supply a timestamp for an insert or update. In schema declarations, its SQL form is `(CURRENT_TIMESTAMP||'Z')`.
* A column default applies only to insertion. Supply `updated_at` or similar values explicitly when updating a row.
* When Python produces a compatible timestamp string, prefer `datetime.isoformat(sep=' ')` over its default `T` separator and ensure that UTC values have the `Z` suffix.
* Use the resolution appropriate to the event. Default to whole seconds, which matches SQLite's `CURRENT_TIMESTAMP` resolution.
* Use one separator, timezone representation, and fractional-second precision within values that will be compared or sorted as text.
* When several statements in one transaction need the identical timestamp, compute one value and reuse it. SQLite only guarantees that its current-time value is stable within one statement, not across an entire transaction.

Date-only values use ISO `YYYY-MM-DD` strings.
Durations are not timestamps; store them in an explicitly named unit appropriate to the domain.

## Application boundaries

Application-owned schemas should follow these conventions directly.
Vendor API mirrors may retain source names, nullable fields, or timestamp formats when faithful synchronization requires them.
Normalize values at a deliberate boundary rather than silently mixing representations in one column.

In general, asyncio requires SQLite operations to run on separate threads.
