# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import importlib
import os
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager

from pithy.fs import make_dirs
from pithy.logs import adjust_log_level
from pithy.sqlite.database import Database, DbConfig
from pithy.sqlite.migrate.main import main_migrate
from pithy.sqlite.migrate.transaction import MigrationError
from pithy.sqlite.schema import Column, Schema, Table
from utest import utest_exc, utest_run, utest_val


def write_migration(d:str, name:str, content:str) -> None:
  with open(os.path.join(d, name), 'w') as f:
    f.write(content)


_migrations_pkg_counter = 0


@contextmanager
def migrations_pkg() -> Generator[tuple[str,str]]:
  '''
  Create a fresh, importable migrations package in a temp dir and yield (package_name, package_dir).
  See the identical helper in versions.ut.py for details.
  '''
  global _migrations_pkg_counter
  _migrations_pkg_counter += 1
  with tempfile.TemporaryDirectory() as root:
    pkg_name = f'migrate_main_ut_pkg_{_migrations_pkg_counter}'
    pkg_dir = os.path.join(root, pkg_name)
    os.mkdir(pkg_dir)
    open(os.path.join(pkg_dir, '__init__.py'), 'w').close()
    sys.path.insert(0, root)
    importlib.invalidate_caches()
    try:
      yield pkg_name, pkg_dir
    finally:
      try: sys.path.remove(root)
      except ValueError: pass
      for name in [n for n in sys.modules if n == pkg_name or n.startswith(pkg_name + '.')]:
        del sys.modules[name]


def make_group_config(root:str, *, user_version:int|None=None) -> DbConfig:
  'Initialize a two-database group under root and return its config.'
  data_dir = os.path.join(root, 'data')
  make_dirs(data_dir)
  config = DbConfig(names=('main', 'aux'), data_dir=data_dir, user_version=user_version)
  with adjust_log_level('warn'): Database.initialize(config)
  return config


def table_names(config:DbConfig, schema:str='main') -> list[str]:
  with Database.ro(config) as db:
    return [row[0] for row in db.conn.execute(
      f"SELECT name FROM {schema}.sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


# check: a valid package passes without a config or database.
@utest_run
def _test_check() -> None:
  py = '''\
from pithy.sqlite import Cursor

def m0002_gadgets(c:Cursor) -> None:
  c.execute('CREATE TABLE gadgets (id INTEGER PRIMARY KEY)')
'''
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_widgets.sql', 'CREATE TABLE widgets (id INTEGER PRIMARY KEY);')
    write_migration(d, 'm0002_gadgets.py', py)
    with adjust_log_level('warn'): main_migrate(pkg, argv=['check'])


# check: a .py migration missing its stem-named function raises.
@utest_run
def _test_check_bad_py_raises() -> None:
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_empty.py', 'x = 1\n')
    utest_exc(MigrationError, main_migrate, pkg, argv=['check'])


# run: applies pending migrations up to config.user_version.
@utest_run
def _test_run() -> None:
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, d):
    config = make_group_config(root, user_version=2)
    write_migration(d, 'm0001_widgets.sql', 'CREATE TABLE main.widgets (id INTEGER PRIMARY KEY);')
    write_migration(d, 'm0002_gadgets.sql', 'CREATE TABLE aux.gadgets (id INTEGER PRIMARY KEY);')
    with adjust_log_level('warn'):
      main_migrate(pkg, config=config, argv=['run'])
      utest_val(['widgets'], table_names(config, 'main'), 'main table created')
      utest_val(['gadgets'], table_names(config, 'aux'), 'aux table created')
      with Database.ro(config) as db:
        utest_val(2, db.conn.cursor().user_version(), 'user_version advanced to 2')


# run -target: stops at the given version.
@utest_run
def _test_run_target() -> None:
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, d):
    config = make_group_config(root, user_version=2)
    write_migration(d, 'm0001_widgets.sql', 'CREATE TABLE widgets (id INTEGER PRIMARY KEY);')
    write_migration(d, 'm0002_gadgets.sql', 'CREATE TABLE gadgets (id INTEGER PRIMARY KEY);')
    with adjust_log_level('error'): # Silences the expected files-beyond-target warning.
      main_migrate(pkg, config=config, argv=['run', '-target', '1'])
      utest_val(['widgets'], table_names(config), 'only version 1 applied')
      with Database.ro(config) as db:
        utest_val(1, db.conn.cursor().user_version(), 'user_version stopped at 1')


# run -rerun: reapplies the latest batch without lowering or raising user_version.
@utest_run
def _test_run_rerun() -> None:
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, d):
    config = make_group_config(root, user_version=2)
    write_migration(d, 'm0001_widgets.sql', 'CREATE TABLE widgets (id INTEGER PRIMARY KEY);')
    write_migration(d, 'm0002_seed.sql', 'INSERT INTO widgets DEFAULT VALUES;')
    with adjust_log_level('warn'):
      main_migrate(pkg, config=config, argv=['run'])
      with Database.ro(config) as db:
        utest_val(1, next(iter(db.conn.execute('SELECT count(*) FROM widgets')))[0], 'one row after run')
      main_migrate(pkg, config=config, argv=['run', '-rerun'])
      with Database.ro(config) as db:
        utest_val(2, next(iter(db.conn.execute('SELECT count(*) FROM widgets')))[0], 'rerun reapplied the latest batch')
        utest_val(2, db.conn.cursor().user_version(), 'user_version unchanged by rerun')


# run -rerun: refuses when pending migrations exist or the target is not the latest version.
@utest_run
def _test_run_rerun_guards() -> None:
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, d):
    config = make_group_config(root, user_version=2)
    write_migration(d, 'm0001_widgets.sql', 'CREATE TABLE widgets (id INTEGER PRIMARY KEY);')
    write_migration(d, 'm0002_gadgets.sql', 'CREATE TABLE gadgets (id INTEGER PRIMARY KEY);')
    with adjust_log_level('warn'):
      utest_exc(MigrationError, main_migrate, pkg, config=config, argv=['run', '-rerun']) # Database is behind.
    with adjust_log_level('error'): # Silences the expected files-beyond-target warning.
      main_migrate(pkg, config=config, argv=['run', '-target', '1'])
      utest_exc(MigrationError, main_migrate, pkg, config=config, argv=['run', '-rerun', '-target', '1']) # Not the latest.


# sync: automigrates the database to the declared schemas and stamps user_version to the latest migration version.
@utest_run
def _test_sync() -> None:
  schema = Schema('main', structures=[
    Table('widgets', columns=(
      Column('id', int, is_primary=True, is_unique=True),
      Column('name', str),
    )),
  ])
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, d):
    config = make_group_config(root)
    write_migration(d, 'm0001_a.sql', '-- placeholder; sync does not run migration files.\n')
    write_migration(d, 'm0002_b.sql', '-- placeholder; sync does not run migration files.\n')
    with adjust_log_level('warn'):
      main_migrate(pkg, config=config, schemas=[schema], argv=['sync'])
      utest_val(['widgets'], table_names(config), 'sync created the table')
      with Database.ro(config) as db:
        c = db.conn.cursor()
        utest_val(2, c.user_version('main'), 'main stamped to latest migration version')
        utest_val(2, c.user_version('aux'), 'aux stamped to latest migration version')


# sync: with no migration files, bootstraps the schemas at version 0.
@utest_run
def _test_sync_bootstrap() -> None:
  schema = Schema('main', structures=[Table('t', columns=(Column('id', int, is_primary=True, is_unique=True),))])
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, d):
    config = make_group_config(root)
    with adjust_log_level('warn'):
      main_migrate(pkg, config=config, schemas=[schema], argv=['sync'])
      utest_val(['t'], table_names(config), 'sync created the table')
      with Database.ro(config) as db:
        utest_val(0, db.conn.cursor().user_version(), 'user_version stays 0 with no migration files')


# sync: without schemas raises.
@utest_run
def _test_sync_without_schemas_raises() -> None:
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, d):
    config = make_group_config(root)
    with adjust_log_level('warn'):
      utest_exc(MigrationError, main_migrate, pkg, config=config, argv=['sync'])


# gen: diffs the live database against the schemas; the database must be at the latest migration version.
@utest_run
def _test_gen() -> None:
  widgets = Table('widgets', columns=(
    Column('id', int, is_primary=True, is_unique=True),
    Column('name', str),
  ))
  gadgets = Table('gadgets', columns=(Column('id', int, is_primary=True, is_unique=True),))
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, d):
    config = make_group_config(root)
    with adjust_log_level('warn'):
      # First generation: the database is empty at version 0 with no migration files; the diff is the initial widgets table.
      main_migrate(pkg, config=config, schemas=[Schema('main', structures=[widgets])], argv=['gen', 'initial'])
      path1 = os.path.join(d, 'm0001_initial.sql')
      utest_val(True, os.path.exists(path1), 'm0001 generated')
      utest_val([], table_names(config), 'gen does not modify the database')
      # The draft m0001 is now pending: the database is behind the latest migration version, so gen refuses.
      utest_exc(MigrationError, main_migrate, pkg, config=config, schemas=[Schema('main', structures=[widgets, gadgets])],
        argv=['gen', 'add_gadgets'])
      # After running the pending migration, gen diffs incrementally: only the new gadgets table.
      main_migrate(pkg, config=config, schemas=[Schema('main', structures=[widgets])], argv=['run', '-target', '1'])
      main_migrate(pkg, config=config, schemas=[Schema('main', structures=[widgets, gadgets])], argv=['gen', 'add_gadgets'])
      path2 = os.path.join(d, 'm0002_add_gadgets.sql')
      utest_val(True, os.path.exists(path2), 'm0002 generated')
      with open(path2) as f:
        content = f.read()
      utest_val(True, 'gadgets' in content, 'diff contains the new table')
      utest_val(False, 'widgets' in content, 'diff excludes the already-migrated table')


# gen: a database ahead of the migration files raises.
@utest_run
def _test_gen_db_ahead_raises() -> None:
  schema = Schema('main', structures=[Table('t', columns=(Column('id', int, is_primary=True, is_unique=True),))])
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, d):
    config = make_group_config(root)
    with adjust_log_level('warn'):
      with Database.rw(config) as db:
        with db.conn:
          c = db.conn.cursor()
          for name in config.names: c.set_user_version(name, 3)
      utest_exc(MigrationError, main_migrate, pkg, config=config, schemas=[schema], argv=['gen'])
