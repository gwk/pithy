# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import importlib
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import closing, contextmanager

from pithy.fs import make_dirs
from pithy.logs import adjust_log_level
from pithy.sqlite.conn import Conn
from pithy.sqlite.database import Database, DbConfig
from pithy.sqlite.migrate.transaction import MigrationError
from pithy.sqlite.migrate.versions import (check_migrations, find_migrations, generate_migration_file, migrate_database,
  MigrationFile, run_versioned_migrations)
from pithy.sqlite.schema import Column, Schema, Table
from utest import utest_exc, utest_run, utest_val


def make_conn() -> Conn:
  return Conn(':memory:', mode='memory')


def write_migration(d:str, name:str, content:str) -> None:
  with open(os.path.join(d, name), 'w') as f:
    f.write(content)


_migrations_pkg_counter = 0


@contextmanager
def migrations_pkg() -> Iterator[tuple[str,str]]:
  '''
  Create a fresh, importable migrations package in a temp dir and yield (package_name, package_dir).
  The package name is unique per call so importlib's module cache does not leak between tests, and the temp dir's
  parent is placed on sys.path so `package_name` and its `.py` submigrations import as a real package.
  '''
  global _migrations_pkg_counter
  _migrations_pkg_counter += 1
  with tempfile.TemporaryDirectory() as root:
    pkg_name = f'versioned_ut_pkg_{_migrations_pkg_counter}'
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


def table_names(conn:Conn, schema:str='main') -> list[str]:
  return [row[0] for row in conn.execute(
    f"SELECT name FROM {schema}.sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


# find_migrations: empty directory returns empty list.
@utest_run
def _test_find_empty() -> None:
  with tempfile.TemporaryDirectory() as d:
    utest_val([], find_migrations(d), 'empty dir')


# find_migrations: valid sequence with a mixed .py/.sql batch, non-migration files ignored.
@utest_run
def _test_find_valid_sequence() -> None:
  with tempfile.TemporaryDirectory() as d:
    for name in ['m0001_a.sql', 'm0001_b.py', 'm0002_c.sql', '__init__.py', 'helpers.py']:
      open(os.path.join(d, name), 'w').close()
    files = find_migrations(d)
    utest_val(3, len(files), 'ignores non-migration files')
    utest_val(MigrationFile(1, 'm0001_a', os.path.join(d, 'm0001_a.sql'), '.sql'), files[0], 'file 1a (sql)')
    utest_val(MigrationFile(1, 'm0001_b', os.path.join(d, 'm0001_b.py'), '.py'), files[1], 'file 1b (py)')
    utest_val(MigrationFile(2, 'm0002_c', os.path.join(d, 'm0002_c.sql'), '.sql'), files[2], 'file 2c (sql)')


# find_migrations: the floor need not be 1, so pruned histories are valid.
@utest_run
def _test_find_pruned_floor() -> None:
  with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'm0007_a.sql'), 'w').close()
    open(os.path.join(d, 'm0008_b.sql'), 'w').close()
    utest_val([7, 8], [f.version for f in find_migrations(d)], 'contiguous versions starting above 1')


# find_migrations: a gap in version numbers raises.
@utest_run
def _test_find_gap_raises() -> None:
  with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'm0001_a.sql'), 'w').close()
    open(os.path.join(d, 'm0003_c.sql'), 'w').close()
    utest_exc(MigrationError, find_migrations, d)


# find_migrations: version 0 raises.
@utest_run
def _test_find_version_zero_raises() -> None:
  with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'm0000_a.sql'), 'w').close()
    utest_exc(MigrationError, find_migrations, d)


# find_migrations: a migration-like name missing the required suffix raises.
@utest_run
def _test_find_missing_suffix_raises() -> None:
  with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'm0001.sql'), 'w').close()
    utest_exc(MigrationError, find_migrations, d)


# find_migrations: a migration-like name that is otherwise malformed raises.
@utest_run
def _test_find_malformed_raises() -> None:
  with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'm0001bad.py'), 'w').close()
    utest_exc(MigrationError, find_migrations, d)


# run_versioned_migrations: a .sql-only sequence applies and updates user_version.
@utest_run
def _test_run_sql_sequence() -> None:
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_create.sql', 'CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT NOT NULL);')
    write_migration(d, 'm0002_add_color.sql', 'ALTER TABLE widgets ADD COLUMN color TEXT;')

    with closing(make_conn()) as conn, adjust_log_level('warn'):
      c = conn.cursor()
      utest_val(0, c.user_version(), 'initial version is 0')

      run_versioned_migrations(conn, pkg, target_version=2)

      utest_val(2, c.user_version(), 'version updated to 2')
      col_names = [row[1] for row in conn.execute("PRAGMA table_info('widgets')")]
      utest_val(True, 'color' in col_names, 'color column added by m0002')


# run_versioned_migrations: a .py migration runs its stem-named migration function.
@utest_run
def _test_run_py_migrate() -> None:
  py = '''\
from pithy.sqlite import Cursor

def m0001_gadgets(c:Cursor) -> None:
  c.execute('CREATE TABLE gadgets (id INTEGER PRIMARY KEY)')
  c.execute("INSERT INTO gadgets (id) VALUES (1), (2)")
'''
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_gadgets.py', py)
    with closing(make_conn()) as conn, adjust_log_level('warn'):
      run_versioned_migrations(conn, pkg, target_version=1)
      utest_val(1, conn.cursor().user_version(), 'version updated to 1')
      count = next(iter(conn.execute('SELECT count(*) FROM gadgets')))[0]
      utest_val(2, count, 'migration function inserted rows')


# run_versioned_migrations: a .py migration can use a relative import to reach a sibling module in its package.
@utest_run
def _test_run_py_relative_import() -> None:
  helper = '''\
from pithy.sqlite import Cursor

def create_widgets(c:Cursor) -> None:
  c.execute('CREATE TABLE widgets (id INTEGER PRIMARY KEY)')
'''
  mig = '''\
from pithy.sqlite import Cursor

from .helpers import create_widgets

def m0001_widgets(c:Cursor) -> None:
  create_widgets(c)
'''
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'helpers.py', helper) # Non-migration sibling; ignored by find_migrations, importable as a submodule.
    write_migration(d, 'm0001_widgets.py', mig)
    with closing(make_conn()) as conn, adjust_log_level('warn'):
      run_versioned_migrations(conn, pkg, target_version=1)
      utest_val(['widgets'], table_names(conn), 'relative import to sibling helper worked')


# run_versioned_migrations: files sharing a version form a batch and bump the version once.
@utest_run
def _test_run_batch() -> None:
  py = '''\
from pithy.sqlite import Cursor

def m0001_b(c:Cursor) -> None:
  c.execute('CREATE TABLE b (id INTEGER PRIMARY KEY)')
'''
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_a.sql', 'CREATE TABLE a (id INTEGER PRIMARY KEY);')
    write_migration(d, 'm0001_b.py', py)
    with closing(make_conn()) as conn, adjust_log_level('warn'):
      run_versioned_migrations(conn, pkg, target_version=1)
      utest_val(1, conn.cursor().user_version(), 'batch bumps version once to 1')
      utest_val(['a', 'b'], table_names(conn), 'both batch files applied')


# run_versioned_migrations: a failure mid-run rolls the whole transaction back.
@utest_run
def _test_run_atomic_rollback() -> None:
  boom = '''\
from pithy.sqlite import Cursor

def m0002_boom(c:Cursor) -> None:
  c.execute('CREATE TABLE u (id INTEGER PRIMARY KEY)')
  raise RuntimeError('boom')
'''
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_create.sql', 'CREATE TABLE t (x INTEGER);')
    write_migration(d, 'm0002_boom.py', boom)
    with closing(make_conn()) as conn, adjust_log_level('silent'): # Silences the expected migration-failure error log.
      c = conn.cursor()
      utest_exc(RuntimeError, run_versioned_migrations, conn, pkg, target_version=2)
      utest_val(0, c.user_version(), 'user_version unchanged after rollback')
      utest_val([], table_names(conn), 'earlier migration rolled back too')


# run_versioned_migrations: a .py file without its stem-named migration function raises.
@utest_run
def _test_run_py_without_fn_raises() -> None:
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_empty.py', 'x = 1\n')
    with closing(make_conn()) as conn, adjust_log_level('silent'): # Silences the expected migration-failure error log.
      utest_exc(MigrationError, run_versioned_migrations, conn, pkg, target_version=1)


# run_versioned_migrations: a .py file whose function name does not match the file stem raises.
@utest_run
def _test_run_py_wrong_fn_name_raises() -> None:
  py = '''\
from pithy.sqlite import Cursor

def migrate(c:Cursor) -> None:
  c.execute('CREATE TABLE t (x INTEGER)')
'''
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_t.py', py)
    with closing(make_conn()) as conn, adjust_log_level('silent'): # Silences the expected migration-failure error log.
      utest_exc(MigrationError, run_versioned_migrations, conn, pkg, target_version=1)


# check_migrations: validates names, contiguity, and .py migration functions without a database.
@utest_run
def _test_check_migrations() -> None:
  py = '''\
from pithy.sqlite import Cursor

def m0002_gadgets(c:Cursor) -> None:
  c.execute('CREATE TABLE gadgets (id INTEGER PRIMARY KEY)')
'''
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_widgets.sql', 'CREATE TABLE widgets (id INTEGER PRIMARY KEY);')
    write_migration(d, 'm0002_gadgets.py', py)
    files = check_migrations(pkg)
    utest_val([1, 2], [f.version for f in files], 'check returns validated files')


# check_migrations: a .py migration without its stem-named function raises.
@utest_run
def _test_check_migrations_missing_fn_raises() -> None:
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_empty.py', 'x = 1\n')
    utest_exc(MigrationError, check_migrations, pkg)


# run_versioned_migrations: already up to date is a no-op.
@utest_run
def _test_already_up_to_date() -> None:
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_create.sql', 'CREATE TABLE t (x INTEGER);')
    with closing(make_conn()) as conn, adjust_log_level('warn'):
      run_versioned_migrations(conn, pkg, target_version=1)
      c = conn.cursor()
      utest_val(1, c.user_version(), 'at version 1 after first run')
      run_versioned_migrations(conn, pkg, target_version=1)
      utest_val(1, c.user_version(), 'still at version 1')


# run_versioned_migrations: DB ahead of target raises.
@utest_run
def _test_db_ahead_raises() -> None:
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_create.sql', 'CREATE TABLE t (x INTEGER);')
    write_migration(d, 'm0002_noop.sql', '-- nothing to do\n')
    with closing(make_conn()) as conn, adjust_log_level('warn'):
      run_versioned_migrations(conn, pkg, target_version=2)
      utest_exc(MigrationError, run_versioned_migrations, conn, pkg, target_version=1)


# run_versioned_migrations: a missing target version raises.
@utest_run
def _test_missing_version_raises() -> None:
  with migrations_pkg() as (pkg, d):
    write_migration(d, 'm0001_create.sql', 'CREATE TABLE t (x INTEGER);')
    with closing(make_conn()) as conn, adjust_log_level('warn'):
      utest_exc(MigrationError, run_versioned_migrations, conn, pkg, target_version=2)


# generate_migration_file: creates a .sql file with correct content when schema has changes.
@utest_run
def _test_generate_with_changes() -> None:
  schema = Schema('main', structures=[
    Table('widgets', columns=(
      Column('id', int, is_primary=True, is_unique=True),
      Column('name', str),
    )),
  ])
  with migrations_pkg() as (pkg, d), closing(make_conn()) as conn, adjust_log_level('warn'):
    path = generate_migration_file(conn, pkg, [schema])
    utest_val(True, path is not None, 'file is generated')
    assert path is not None
    utest_val(True, path.endswith('m0001_migration.sql'), 'file named with default description and .sql suffix')
    with open(path) as f:
      content = f.read()
    utest_val(True, 'CREATE TABLE' in content, 'contains CREATE TABLE')
    utest_val(True, 'widgets' in content, 'mentions table name')


# generate_migration_file: refuses when the database is not at the latest migration version.
@utest_run
def _test_generate_guard() -> None:
  schema = Schema('main', structures=[
    Table('widgets', columns=(Column('id', int, is_primary=True, is_unique=True),)),
  ])
  with migrations_pkg() as (pkg, d), closing(make_conn()) as conn, adjust_log_level('warn'):
    write_migration(d, 'm0001_widgets.sql', 'CREATE TABLE widgets (id INTEGER PRIMARY KEY);')
    utest_exc(MigrationError, generate_migration_file, conn, pkg, [schema]) # Behind: pending m0001 has not been run.
    conn.run_effect('PRAGMA user_version = 2')
    utest_exc(MigrationError, generate_migration_file, conn, pkg, [schema]) # Ahead: user_version exceeds latest migration.


# generate_migration_file: returns None when schema matches DB.
@utest_run
def _test_generate_no_changes() -> None:
  schema = Schema('main', structures=[
    Table('widgets', columns=(
      Column('id', int, is_primary=True, is_unique=True),
      Column('name', str),
    )),
  ])
  with migrations_pkg() as (pkg, d), closing(make_conn()) as conn, adjust_log_level('warn'):
    # Generate and apply the first migration.
    path1 = generate_migration_file(conn, pkg, [schema])
    assert path1 is not None
    run_versioned_migrations(conn, pkg, target_version=1)
    # Schema now matches; second generate should return None.
    path2 = generate_migration_file(conn, pkg, [schema], description='should_not_exist')
    utest_val(None, path2, 'no file when schema matches DB')


# generate_migration_file: description is included in filename.
@utest_run
def _test_generate_with_description() -> None:
  schema = Schema('main', structures=[
    Table('events', columns=(Column('id', int, is_primary=True, is_unique=True),)),
  ])
  with migrations_pkg() as (pkg, d), closing(make_conn()) as conn, adjust_log_level('warn'):
    path = generate_migration_file(conn, pkg, [schema], description='add_events')
    utest_val(True, path is not None, 'file generated')
    assert path is not None
    utest_val(True, path.endswith('m0001_add_events.sql'), 'description in filename')


def make_group_config(root:str, *, user_version:int|None=None) -> DbConfig:
  'Initialize a two-database group under root and return its config.'
  data_dir = os.path.join(root, 'data')
  make_dirs(data_dir)
  config = DbConfig(names=('main', 'aux'), data_dir=data_dir, user_version=user_version)
  with adjust_log_level('warn'): Database.initialize(config)
  return config


# migrate_database: runs across an attached group and bumps user_version on every member, targeting config.user_version.
@utest_run
def _test_migrate_database_group() -> None:
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, mig_dir):
    config = make_group_config(root, user_version=2)
    write_migration(mig_dir, 'm0001_main.sql', 'CREATE TABLE main.widgets (id INTEGER PRIMARY KEY);')
    write_migration(mig_dir, 'm0002_aux.sql', 'CREATE TABLE aux.gadgets (id INTEGER PRIMARY KEY);')

    with adjust_log_level('warn'): migrate_database(pkg, config=config) # target_version defaults to config.user_version (2).

    with Database.ro(config) as db:
      c = db.conn.cursor()
      utest_val(2, c.user_version('main'), 'main user_version advanced to 2')
      utest_val(2, c.user_version('aux'), 'aux user_version advanced to 2')
      utest_val(['widgets'], table_names(db.conn, 'main'), 'main table created')
      utest_val(['gadgets'], table_names(db.conn, 'aux'), 'aux table created')


# migrate_database: a failure mid-run rolls back schema and user_version across the whole group.
@utest_run
def _test_migrate_database_group_rollback() -> None:
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, mig_dir):
    config = make_group_config(root)
    write_migration(mig_dir, 'm0001_main.sql', 'CREATE TABLE main.widgets (id INTEGER PRIMARY KEY);')
    write_migration(mig_dir, 'm0002_bad.sql', 'CREATE TABLE aux.gadgets (id INTEGER PRIMARY KEY);\nSELECT bad_fn();')

    with adjust_log_level('silent'): # Silences the expected migration-failure error log.
      utest_exc(Exception, migrate_database, pkg, config=config, target_version=2)

    with Database.ro(config) as db:
      c = db.conn.cursor()
      utest_val(0, c.user_version('main'), 'main user_version unchanged after rollback')
      utest_val(0, c.user_version('aux'), 'aux user_version unchanged after rollback')
      utest_val([], table_names(db.conn, 'main'), 'main change rolled back')
      utest_val([], table_names(db.conn, 'aux'), 'aux change rolled back')


# migrate_database: no target_version and no config.user_version is an error.
@utest_run
def _test_migrate_database_no_target() -> None:
  with tempfile.TemporaryDirectory() as root, migrations_pkg() as (pkg, mig_dir):
    config = make_group_config(root)
    with adjust_log_level('warn'):
      utest_exc(MigrationError, migrate_database, pkg, config=config)
