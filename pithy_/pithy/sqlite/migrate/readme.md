# pithy.sqlite.migrate

This module supports versioned schema migrations for `pithy.sqlite` database groups.
It provides a CLI implementation for running migrations in transactions,
and a migration generator that diffs the current database against the schemas declared in application code.

The design assumes that developers will author and test migrations against recent backups with representative data.
It does not require or enforce that a database can be rebuilt from the full migration history.

Old migrations that are no longer necessary and present maintenance problems may be pruned.
This bounds the "code rot" problem for migrations that call application code:
only migrations in the recent window between the oldest restorable backup and HEAD must be retained.

The developer is responsible for database state: the workflow starts from a current/restored copy,
and recovery from a bad migration is another restore. The tool checks that the database matches the checked-in
migration history at each step, so accidental departures from the workflow are caught early.

## Project setup

1. Create a migrations package inside the application, e.g. `myapp/migrations/__init__.py`.
   It must be a regular package (a single directory). Its `.py` migrations are imported as submodules,
   so they can use relative and absolute imports to reach application code (validators, converters, etc.).

2. Declare the database group as a `DbConfig`, including `user_version`: the schema version the application code expects.

3. Declare the schemas as `pithy.sqlite.schema.Schema` structures.

4. Add a migration script to the project that calls `main_migrate`:

```python
from myapp import config, schemas
from myapp import migrations
from pithy.sqlite.migrate.main import main_migrate

if __name__ == '__main__': main_migrate(migrations, config=config, schemas=schemas)
```

The script must run in the application's environment, because `.py` migrations can import application code.

## Migration files

* Files are named `m<number>_<description>.py|sql`, e.g. `m0007_add_events.sql`. The description suffix is required.
* Multiple files may share a version number; they form a batch that runs together, ordered by name.
* Versions must be contiguous with no gaps. The floor need not be 1: old migrations may be pruned
  once no restorable backup predates them.
* A `.sql` file is executed as a script.
* A `.py` file must define a function named after its file stem, e.g. `def m0007_backfill(c:Cursor) -> None`.
  The stem-named function makes the migration identifiable in stack traces.
* All pending batches run in a single transaction with foreign keys disabled and a `foreign_key_check` before commit;
  any failure rolls the entire run back. `user_version` advances across every database in the group as each batch completes.

## Commands

* `check`: validate the migrations package without touching a database: file naming, version contiguity,
  and that each `.py` migration imports cleanly and defines its stem-named function.
* `run [-target N] [-rerun] [-dry-run]`: run all pending versioned migrations; the target defaults to `config.user_version`.
  After migrating to the latest version, the database is diffed against the declared schemas and any remaining drift
  is reported as a warning: the migration files should produce exactly the declared schemas.
  `-rerun` instead reapplies the latest batch even though the stored `user_version` already covers it;
  this is a shortcut around the restore-and-run cycle for iterating on edits to the current migration.
  A failed rerun rolls back, but a successful reapply of a non-idempotent batch will corrupt the database.
* `gen [description]`: generate the next numbered migration file by diffing the database against the declared schemas.
  Refuses unless the database `user_version` equals the latest migration file version; see the workflow below.
* `sync [-dry-run]`: diff the live database against the declared schemas, apply the difference, and update
  `user_version` across the group to the latest migration file version, in a single transaction.
  Sync does not run any migration files. It is useful for reconciling a drifted database or adopting an existing one.

## Development workflow

The dev database is kept in a known state: restored from a backup of production, and therefore matching the
checked-in migration history. All iteration is restore-based.

1. Restore the dev database from production (or the cached local copy of it). It is now at version N,
   with migrations m1..mN applied. If teammate migrations are pending after a pull, run `run` first.
2. Edit the schema declarations in application code.
3. Run `gen <description>`: it diffs the database against the declared schemas and writes `m<N+1>_<description>.sql`.
4. Review (and edit if needed) the generated file. Bump the application's declared `user_version` to N+1.
5. Run `run` and inspect the results.
6. If the migration is wrong: restore again, then either hand-edit the file and run `run` again,
   or delete the file, adjust the schemas, and regenerate.
   If the batch is idempotent, `run -rerun` reapplies it without a restore.
7. Commit the migration file together with the schema and `user_version` changes.

`gen` refuses to run unless the database `user_version` equals the latest migration file version.
This catches the common mistakes: forgetting to restore, generating on top of an unapplied draft
(which would stack a second pending version), and running against a database left by another branch.
The intended state is always version N (clean) or N+1 (one draft migration in progress).

### Data migrations

For migrations that transform existing data, especially semantic fixes written in Python:

1. Author the batch for version N+1: the generated `.sql` for structural changes,
   plus hand-written `.py` files for the data transformations, sharing the same version number.
2. Run `run` and inspect the results.
3. To iterate: restore (back to version N) and run again; or, if the batch is idempotent, `run -rerun` skips the restore.

## Deployment

Run `run` during deploy. The target defaults to the application's declared `user_version`.
A deploy that spans multiple versions replays each pending checked-in step in order;
intermediate schemas are never recomputed, because each step's diff was generated at development time.
Everything runs in one transaction, so a failed deploy leaves the database untouched.
The post-run drift check warns if the migrated database does not match the declared schemas.

`sync` is deliberately not part of the deploy path. For a database with unexpected drift
(a manual change, or an existing database being ported to this system), reconcile explicitly:
`sync` moves it to the declared schemas and stamps it to the current version.
