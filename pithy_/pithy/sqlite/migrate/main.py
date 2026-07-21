# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Reusable CLI entry point for project migration commands.

A project defines its own migration script that calls `main_migrate` with its migrations package, config and schemas:

  from myapp import config, schemas
  from myapp import migrations
  from pithy.sqlite.migrate.main import main_migrate

  if __name__ == '__main__': main_migrate(migrations, config=config, schemas=schemas)

The script must run in the application's environment because .py migrations import application code.
'''

import types
from argparse import Namespace
from typing import Iterable, Sequence

from ...argparser import CommandParser
from ...logs import logI, logW
from ..database import Database, DbConfig
from ..schema import Schema
from .transaction import MigrationError
from .versions import check_migrations, generate_migration_file, migrate_database, sync_database


def main_migrate(migrations:types.ModuleType|str, *, config:DbConfig|None=None, schemas:Iterable[Schema]|None=None,
 argv:Sequence[str]|None=None) -> None:
  '''
  Parse a migration command verb from argv (defaulting to sys.argv) and execute it.

  Commands:
  * check: validate the migrations package without touching the database.
  * run: run all pending versioned migrations up to the target version, then check the result against the schemas.
    The -rerun flag instead reapplies the latest (presumably idempotent) batch, for quick iteration on its files.
  * gen: generate the next versioned migration file by diffing the database against the schemas.
  * sync: automigrate the database to the current schemas and update `user_version` to the latest migration version;
    use it to reconcile a drifted database without a formal migration.

  config defaults to `Database.global_config()` for the commands that open the database;
  check does not require a config, but uses one if provided to compare its user_version against the latest migration.
  '''

  def get_config() -> DbConfig:
    return config or Database.global_config()

  def main_check(args:Namespace) -> None:
    'Check that the migration files are well-formed: names, version contiguity, and .py migration functions.'
    files = check_migrations(migrations)
    latest = max((f.version for f in files), default=0)
    logI('Checked migration files.', count=len(files), latest_version=latest)
    if config is not None and config.user_version is not None and config.user_version != latest:
      logW('Latest migration version does not match the configured user_version.', latest=latest,
        user_version=config.user_version)

  def main_run(args:Namespace) -> None:
    'Run all pending versioned migrations, then check the result against the schemas (if provided).'
    migrate_database(migrations, config=get_config(), target_version=args.target, schemas=schemas, rerun=args.rerun,
      dry_run=args.dry_run)

  def main_gen(args:Namespace) -> None:
    'Generate the next versioned migration file by diffing the database against the current schemas.'
    # The database must be at the latest checked-in migration version, typically a freshly restored copy of production;
    # see generate_migration_file. The database itself is not modified.
    if schemas is None:
      raise MigrationError('The gen command requires schemas, but none were provided to main_migrate.')
    cfg = get_config()
    with Database.ro(cfg) as db:
      generate_migration_file(db.conn, migrations, schemas, description=args.description,
        declared_user_version=cfg.user_version)

  def main_sync(args:Namespace) -> None:
    'Automigrate the database to the current schemas and update user_version to the latest migration version.'
    if schemas is None:
      raise MigrationError('The sync command requires schemas, but none were provided to main_migrate.')
    sync_database(migrations, config=get_config(), schemas=schemas, dry_run=args.dry_run)

  parser = CommandParser(prog='migrate', description='Database migration tool.')

  parser.add_command(main_check)

  command_run = parser.add_command(main_run)
  command_run.add_argument('-target', type=int, default=None, help='Target version; defaults to config.user_version.')
  command_run.add_argument('-rerun', action='store_true',
    help='Reapply the latest (presumably idempotent) batch without a restore; a shortcut for iterating on its files.')
  command_run.add_argument('-dry-run', action='store_true', help='Print pending migrations without applying them.')

  command_gen = parser.add_command(main_gen)
  command_gen.add_argument('description', nargs='?', default='',
    help="Description suffix for the generated file name; defaults to 'migration'.")

  command_sync = parser.add_command(main_sync)
  command_sync.add_argument('-dry-run', action='store_true', help='Print sync statements without applying them.')

  parser.parse_and_run_command(argv)
