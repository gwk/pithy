# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

_context_keywords_ = ['database', 'dry run', 'migration generation', 'python migrations', 'schema drift', 'schema sync',
  'sql migrations', 'user_version', 'versioned migrations']

import re
import types
from dataclasses import dataclass
from importlib import import_module
from itertools import groupby
from typing import Callable, cast, Iterable

from ...fs import list_dir
from ...io import read_from_path
from ...logs import logE, logI, logW
from ...path import path_join, split_stem_ext
from .. import Conn, Cursor
from ..database import Database, DbConfig, set_all_user_versions
from ..schema import Schema
from .gen import find_unreadable_tables, gen_migration, GenMigrationError
from .transaction import migration_transaction, MigrationError


_mig_name_re = re.compile(r'm(\d+)(_\w+)')
_mig_candidate_re = re.compile(r'm\d')


@dataclass(frozen=True)
class MigrationFile:
  '''
  A single versioned migration file.
  version: 1-based; files sharing a version form a batch that runs together.
  name: file stem, e.g. 'm0001_initial'.
  path: absolute path to the source file.
  ext: The path extension ('.py' | '.sql').
  '''
  version: int
  name: str
  path: str
  ext: str


def find_migrations(mig_dir:str) -> list[MigrationFile]:
  '''
  Find and validate migration files in mig_dir.
  Files must be named m<number>_<description>.{py|sql} with N >= 1 and a required description suffix.
  Multiple files may share a version number; they form a batch that runs together, ordered by name.
  The set of distinct versions must be contiguous with no gaps.
  The floor need not be 1: migrations older than any restorable backup may be pruned.
  Files whose names do not begin with 'm' followed by a digit (e.g. __init__.py, helpers.py) are ignored.
  A name that begins with 'm' and a digit but does not fully match the pattern raises MigrationError.
  '''
  files:list[MigrationFile] = []
  for name in list_dir(mig_dir, exts=('.py', '.sql')):
    stem, ext = split_stem_ext(name)
    m = _mig_name_re.fullmatch(stem)
    if not m:
      if _mig_candidate_re.match(stem):
        raise MigrationError(f'Migration file {name!r} does not match the required pattern m<digits>_<description>.(py|sql).')
      continue
    files.append(MigrationFile(version=int(m.group(1)), name=stem, path=path_join(mig_dir, name), ext=ext))

  files.sort(key=lambda f: (f.version, f.name))

  distinct = sorted(set(f.version for f in files))
  if distinct:
    if distinct[0] < 1:
      raise MigrationError(f'Migration versions must be >= 1: found {distinct}.')
    for expected, v in enumerate(distinct, distinct[0]):
      if v != expected:
        raise MigrationError(f'Migration versions are not contiguous: found {distinct}.')

  return files


def resolve_migrations(migrations:types.ModuleType|str) -> tuple[str,str]:
  '''
  Resolve a migrations package to (package_name, directory).
  `migrations` is either the imported package or its dotted module name (e.g. 'myapp.migrations').
  The package must be importable and regular (a single-directory __path__); its .py migrations are imported as
  submodules so they can use relative and absolute imports to reach application code (validators, converters, etc.).
  '''
  mod = import_module(migrations) if isinstance(migrations, str) else migrations
  paths = list(getattr(mod, '__path__', None) or ())
  if len(paths) != 1:
    raise MigrationError(f'Migrations must be a package with a single path; {mod.__name__!r} has __path__={paths!r}.')
  return mod.__name__, paths[0]


def load_migration_module(pkg_name:str, mf:MigrationFile) -> types.ModuleType:
  'Import a .py migration as a submodule of pkg_name so it runs with full package context.'
  full = f'{pkg_name}.{mf.name}'
  try:
    return import_module(full)
  except Exception as e:
    e.add_note(f'Error importing migration module {full!r} (from {mf.path!r}).')
    raise


def get_migration_fn(pkg_name:str, mf:MigrationFile) -> Callable[[Cursor],None]:
  '''
  Import a .py migration and return its migration function.
  The function must be named after the file stem, e.g. `def m0001_initial(c:Cursor) -> None`;
  the stem-named function makes the migration identifiable in stack traces.
  '''
  mod = load_migration_module(pkg_name, mf)
  fn = getattr(mod, mf.name, None)
  if not callable(fn):
    raise MigrationError(f'{mf.name}: .py migration must define a function named after the file stem: {mf.name}(c:Cursor).')
  return cast(Callable[[Cursor],None], fn)


def run_migration_file(c:Cursor, pkg_name:str, mf:MigrationFile) -> None:
  '''
  Run a single migration file against cursor c, within the caller's transaction.
  A .sql file is executed as a script.
  A .py file is imported as a submodule of `pkg_name` and must define its stem-named migration function;
  see `get_migration_fn`.
  '''
  if mf.ext == '.sql':
    c.executescript(read_from_path(mf.path))
  elif mf.ext == '.py':
    get_migration_fn(pkg_name, mf)(c)
  else:
    raise ValueError(mf.ext)


def check_migrations(migrations:types.ModuleType|str) -> list[MigrationFile]:
  '''
  Validate the migrations package without touching a database.
  File names must be well-formed and version-contiguous (see `find_migrations`),
  and each .py migration must import cleanly and define its stem-named migration function.
  Returns the validated files.
  '''
  pkg_name, mig_dir = resolve_migrations(migrations)
  files = find_migrations(mig_dir)
  for mf in files:
    if mf.ext == '.py':
      get_migration_fn(pkg_name, mf)
  return files


def run_versioned_migrations(conn:Conn, migrations:types.ModuleType|str, *, target_version:int,
 schemas:Iterable[Schema]|None=None, db_names:Iterable[str]=('main',), rerun:bool=False, dry_run:bool=False,
 trial:bool=False) -> None:
  '''
  Run pending versioned migrations from the migrations package up to target_version.

  Reads the stored user_version from conn, then runs each pending version's batch of files in order.
  All pending batches run inside a single transaction: any failure rolls the entire run back, leaving
  user_version and the schema untouched. user_version is bumped to N on every database named in db_names
  after each version N's batch completes; pass the whole attached group so its databases advance together.
  For group-aware migration that opens the handle, resolves db_names, and holds the lock, use `migrate_database`.

  rerun is a dangerous shortcut around the restore-and-run cycle, for quickly iterating on edits to the
  latest migration: it reapplies the latest batch even though the stored user_version already covers it.
  A failed rerun rolls back, but a successful reapply of a non-idempotent batch will corrupt the database;
  the safe alternative is always to restore and run again.
  It requires that target_version is the latest migration version and that the database is already at it.

  Raises MigrationError if the DB is ahead of target_version or if any required version is missing.

  Before commit, the stored definition of every table in db_names is checked with `check_tables_readable`.
  If a table that the schemas declare is unreadable at that point, MigrationError is raised and the run rolls back.
  This applies whether the run made the table unreadable or it was unreadable beforehand.
  A batch that repairs such a table passes, because only the state after the batches is checked.

  If schemas is provided and the target is the latest migration version, the database is also diffed against the schemas
  before commit and any remaining drift is reported as a warning:
  the migration files should produce exactly the declared schemas.

  trial runs the pending batches and all of the checks, prints the statements of any remaining drift, and then rolls back.
  It is for iterating on a migration without a restore between attempts.
  Effects that a migration has outside the database are not undone.
  '''
  if trial and dry_run: raise MigrationError('trial and dry_run are mutually exclusive.')
  pkg_name, mig_dir = resolve_migrations(migrations)
  files = find_migrations(mig_dir)
  c = conn.cursor()
  stored_version:int = c.user_version()
  db_names_list = list(db_names)

  if stored_version > target_version:
    raise MigrationError(
      f'Database user_version {stored_version} exceeds target_version {target_version}; cannot migrate backwards.')

  latest = max((f.version for f in files), default=0)
  if latest > target_version:
    logW('Migration files exist beyond the target version; should the configured user_version be bumped?',
      latest=latest, target=target_version)

  schemas_list = None if schemas is None else list(schemas)
  check_schemas = schemas_list if (schemas_list is not None and target_version == latest) else []
  #^ Drift is only meaningful at the latest version, which is the one that the declared schemas describe.
  drift:list[str] = []

  batches = {v: list(g) for v, g in groupby(files, key=lambda f: f.version)}
  pending:list[tuple[int,list[MigrationFile]]] = []
  if rerun:
    if not files:
      raise MigrationError('rerun: no migration files found.')
    if target_version != latest:
      raise MigrationError(f'rerun: can only rerun the latest migration version {latest}; target is {target_version}.')
    if stored_version != latest:
      raise MigrationError(
        f'rerun: database user_version {stored_version} does not match the latest migration version {latest}; '
        'run pending migrations normally first.')
    pending.append((latest, batches[latest]))
  else:
    for v in range(stored_version + 1, target_version + 1):
      if v not in batches:
        raise MigrationError(f'No migration file found for version {v} (stored={stored_version}, target={target_version}).')
      pending.append((v, batches[v]))

  if pending:
    if dry_run:
      for v, batch in pending:
        for mf in batch:
          if mf.ext == '.sql':
            print(f'-- dry run: {mf.name}.sql')
            print(read_from_path(mf.path))
          elif mf.ext == '.py':
            print(f'-- dry run: python migration {mf.name}')
          else:
            raise ValueError(mf.ext)
    else:
      logI('Running versioned migrations.', target=target_version)
      try:
        with migration_transaction(conn, trial=trial) as mc:
          for v, batch in pending:
            for mf in batch:
              logI(f'Running migration {mf.name}.')
              run_migration_file(mc, pkg_name, mf)
            set_all_user_versions(mc, db_names_list, v)
          check_tables_readable(mc, db_names_list, schemas_list)
          drift = find_drift(conn, check_schemas)
      except Exception as e:
        logE('Migration failed.', exc=e)
        raise
      if trial: logI('Trial complete; all changes were rolled back.', version=stored_version)
      else: logI('Versioned migrations complete.', version=target_version)
  else:
    logI('No pending versioned migrations.', version=stored_version)
    if dry_run: return
    check_tables_readable(conn.cursor(), db_names_list, schemas_list)
    drift = find_drift(conn, check_schemas)

  if n := sum(not s.startswith('--') for s in drift):
    if trial:
      for stmt in drift: print(stmt + ('' if stmt.startswith('--') else ';'))
      logW(f'Database does not match the declared schemas after migration ({n} statements). '
        'The migration files are incomplete or the database has drifted; the differences are printed above.')
    else:
      logW(f'Database does not match the declared schemas after migration ({n} statements). '
        'The migration files are incomplete or the database has drifted; run `sync -dry-run` to view the differences.')


def check_tables_readable(c:Cursor, db_names:Iterable[str], schemas:Iterable[Schema]|None) -> None:
  '''
  Raise MigrationError if the schema parser cannot read a table that the schemas declare; see `find_unreadable_tables`.

  The generator cannot diff an unreadable declared table, so later migrations could not be generated or checked for drift.
  An unreadable table that no schema declares is reported as a warning, because the generator never reads it.
  If schemas is None then no table is declared, so every unreadable table is reported as a warning.
  '''
  declared = {(schema.name, table.name) for schema in (schemas or ()) for table in schema.tables}
  errors = []
  for key, reason in find_unreadable_tables(c, db_names).items():
    if key in declared: errors.append(reason)
    else: logW('An undeclared table has a stored definition that the schema parser cannot read.', reason=reason)
  if errors:
    raise MigrationError('\n'.join(('The database contains declared tables that the schema parser cannot read.', *errors,
      'Rewrite each table definition in the form that `gen` produces, or extend the parser.')))


def find_drift(conn:Conn, schemas:Iterable[Schema]) -> list[str]:
  '''
  Return the statements that would migrate the database to the declared schemas; the database should already match exactly.
  If the generator cannot express the difference, this is reported as a warning.
  '''
  try: return [s for schema in schemas for s in gen_migration(conn=conn, schema=schema)]
  except GenMigrationError as e:
    logW('The drift check could not be completed.', error='\n'.join((str(e), *getattr(e, '__notes__', ()))))
    return []


def sync_database(migrations:types.ModuleType|str, *, config:DbConfig|None=None, schemas:Iterable[Schema],
 dry_run:bool=False) -> None:
  '''
  Sync the database group to the declared schemas: automigrate any drift and update user_version to the latest
  migration file version, in a single transaction. Does not run any migration files.

  This is an escape hatch for a database with unexpected drift (a manual change, or an existing database being
  ported to this system); it is not part of the normal workflow, which authors versioned migrations with gen.
  With an empty migrations package it bootstraps: the database is moved to the declared schemas at version 0.

  Before commit, the stored definition of every table is checked with `check_tables_readable`.
  Generated definitions should always be readable, so a failure here indicates a bug in the generator or the parser.
  A declared table that is unreadable beforehand already fails in the generator, before anything is applied.

  When dry_run, the statements are printed and nothing is applied.
  '''
  config = config or Database.global_config()
  schemas = list(schemas)
  _pkg_name, mig_dir = resolve_migrations(migrations)
  version = max((f.version for f in find_migrations(mig_dir)), default=0)
  open_handle = Database.ro if dry_run else Database.rw
  with open_handle(config) as db:
    stmts = [s for schema in schemas for s in gen_migration(conn=db.conn, schema=schema)]
    if dry_run:
      for stmt in stmts:
        print(stmt + ('' if stmt.startswith('--') else ';'))
      logI('Sync dry run; would update user_version.', version=version)
      return
    with migration_transaction(db.conn) as c:
      for stmt in stmts: c.execute(stmt)
      set_all_user_versions(c, config.names, version)
      check_tables_readable(c, config.names, schemas)
  logI('Sync complete.', version=version)


def migrate_database(migrations:types.ModuleType|str, *, config:DbConfig|None=None, target_version:int|None=None,
 schemas:Iterable[Schema]|None=None, rerun:bool=False, dry_run:bool=False, trial:bool=False) -> None:
  '''
  Open a read-write handle to the database group and run versioned migrations from the migrations package.

  config defaults to `Database.global_config()`, so an application that has registered its config
  (or a config loaded from a manifest via `DbConfig.load_manifest`) can migrate with just a migrations package.

  target_version defaults to `config.user_version`, the schema version the application declares;
  it is an error for both to be None.
  `user_version` is advanced across every database in the group (`config.names`) as each batch commits,
  so the group stays in sync.

  rerun reapplies the latest batch without a restore; see `run_versioned_migrations` for the caveats.
  trial runs the migrations and checks, then rolls back; see `run_versioned_migrations`.

  Locking: the handle takes the group's *shared* advisory lock, and that is sufficient.
  The migration runs inside a single immediate transaction, so SQLite locking serializes it against concurrent writers.
  The shared advisory lock only needs to exclude the offline file operations that take the exclusive lock
  (backup restoration, file movement, WAL cleanup), which bypass SQLite's locking entirely.
  '''
  config = config or Database.global_config()
  if target_version is None:
    target_version = config.user_version
    if target_version is None:
      raise MigrationError('migrate_database: no target_version given and config.user_version is None.')

  with Database.rw(config) as db: # Shared advisory lock; see the docstring for why exclusive is not required.
    run_versioned_migrations(db.conn, migrations, target_version=target_version, schemas=schemas, db_names=config.names,
      rerun=rerun, dry_run=dry_run, trial=trial)


def generate_migration_file(conn:Conn, migrations:types.ModuleType|str, schemas:Iterable[Schema], *,
 description:str='', declared_user_version:int|None=None) -> str|None:
  '''
  Generate the next numbered migration .sql file by diffing conn against schemas.
  The file is written into the migrations package directory.

  The database user_version must equal the latest migration file version: the database must reflect exactly
  the checked-in migration history (typically a freshly restored copy of production, migrated if necessary),
  so the diff captures exactly the schema changes not yet expressed as a migration.
  This also refuses to stack a second draft on top of an unapplied one: the working state is always
  version N (clean) or N+1 (one draft migration in progress).

  If declared_user_version is given and does not match the new version, a reminder to bump it is logged.
  Returns the path to the generated file, or None if there are no schema changes.
  '''
  _pkg_name, mig_dir = resolve_migrations(migrations)
  files = find_migrations(mig_dir)
  latest = max((f.version for f in files), default=0)
  stored:int = conn.cursor().user_version()
  if stored < latest:
    raise MigrationError(
      f'gen: database user_version {stored} is behind the latest migration version {latest}; '
      'run pending migrations first (or delete an unapplied draft).')
  if stored > latest:
    raise MigrationError(
      f'gen: database user_version {stored} is ahead of the latest migration version {latest}; '
      'restore the database to a state matching the checked-in migrations.')

  all_stmts:list[str] = []
  for schema in schemas:
    stmts = gen_migration(conn=conn, schema=schema)
    if stmts:
      all_stmts.append(f'-- schema: {schema.name}')
      all_stmts.extend(stmts)

  if not all_stmts:
    logI('No schema changes detected; no migration file generated.')
    return None

  next_version = latest + 1
  description = description or 'migration'
  if not re.fullmatch(r'\w+', description):
    raise MigrationError(f'Invalid migration description {description!r}; must match \\w+.')
  name = f'm{next_version:04d}_{description}'
  path = path_join(mig_dir, f'{name}.sql')

  header = '-- Generated by pithy.sqlite.migrate.versions.'
  body = '\n'.join(stmt + ('' if stmt.startswith('--') else ';') for stmt in [header, *all_stmts]) + '\n'

  with open(path, 'w') as f:
    f.write(body)

  logI('Generated migration file.', path=path)
  if declared_user_version is not None and declared_user_version != next_version:
    logW('Update the configured user_version to match the new migration.', configured=declared_user_version, new=next_version)
  return path
