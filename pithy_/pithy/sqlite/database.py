# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Callable, ClassVar, Iterable, Self

from ..advisory_lock import acquire_advisory_lock, advisory_lock, release_advisory_lock
from ..frozendicts import frozendict
from ..fs import file_size, is_file, move_file, path_exists
from ..logs import logI, logW
from ..path import path_join
from ..sqlite import Conn, Cursor, Mode, Row
from ..strings import format_byte_count
from ..task import run


_convenience_exports = (Cursor, Row)


@dataclass(frozen=True)
class DbConfig:
  'Configuration for a collection of SQLite database files managed together.'

  names: tuple[str, ...]  # Logical db names; must start with 'main'.
  data_dir: str           # Directory containing the .db files.
  user_version: int       # Static schema version for migration tracking.
  cache_mb: int = 256
  synchronous_full: bool = False  # True: fully durable WAL; False: NORMAL (default).
  lock_allow_group: bool = True   # Create the advisory lock sentinel group-accessible (mode 0o660).


  def __post_init__(self) -> None:
    if not self.names or self.names[0] != 'main':
      raise ValueError(f'DbConfig.names must start with "main"; got {self.names!r}.')


  def path(self, name:str) -> str:
    return path_join(self.data_dir, f'{name}.db')


  @property
  def lock_path(self) -> str:
    'Path to the advisory lock sentinel file for this database cluster.'
    return path_join(self.data_dir, '_db.lock')


  @property
  def paths(self) -> frozendict[str,str]:
    return frozendict({name: self.path(name) for name in self.names})


  def shared_lock(self, *, blocking:bool=True) -> AbstractContextManager[None]:
    'Context manager holding the shared cluster advisory lock without opening a connection.'
    return advisory_lock(self.lock_path, exclusive=False, blocking=blocking, allow_group=self.lock_allow_group)


  def exclusive_lock(self, *, blocking:bool=True) -> AbstractContextManager[None]:
    '''
    Context manager holding the exclusive cluster advisory lock without opening a connection.

    For offline operations that manipulate the database files directly, such as restoring from a backup,
    where a connection must not be held. Blocks until all other handles release, then excludes them for the block's duration.
    '''
    return advisory_lock(self.lock_path, exclusive=True, blocking=blocking, allow_group=self.lock_allow_group)


class Database:

  _global_config:ClassVar[DbConfig|None] = None
  _global_config_lazy:ClassVar[tuple[Callable[[],DbConfig],]|None] = None # Wrapped in a tuple to avoid binding errors.


  @classmethod
  def set_global_config(cls, config:DbConfig|Callable[[],DbConfig]) -> None:
    'Set global config or a zero-argument factory callable used when no explicit config is passed.'
    if callable(config):
      cls._global_config_lazy = (config,)
    else:
      assert isinstance(config, DbConfig)
      cls._global_config = config


  @classmethod
  def global_config(cls) -> DbConfig:
    '''
    Return the global configuration if set.
    Otherwise, if there is a lazy config callable, evaluate it, set the global configuration, and return it.
    Otherwise raise a ValueError.
    '''
    if cfg := cls._global_config: return cfg
    if cfg_fn_tuple := cls._global_config_lazy:
      cfg_fn = cfg_fn_tuple[0]
      cfg = cfg_fn()
      cls._global_config = cfg
      return cfg
    raise ValueError('Database: no global config is set.')


  def __init__(self, config:DbConfig|None=None, *, rw:bool=False, exclusive:bool=False, trace_caller_level:int=3) -> None:
    '''
    Open a handle to the database cluster, holding a cluster-wide advisory lock for the handle's lifetime.

    Normal handles take a shared lock (`exclusive=False`); concurrent handles coexist while a shared lock is held.
    File maintenance operations (e.g. backup restorations, movement, WAL cleanup) must use `exclusive=True`,
    which blocks until all shared holders release and excludes all other handles for its duration.

    Within a single process, opening a handle whose lock conflicts with one already open raises `AdvisoryLockError`:
    * exclusive against any open handle
    * shared against an open exclusive handle
    Two shared handles coexist. See `acquire_advisory_lock` for the conflict semantics.
    '''
    config = config or self.global_config()
    self.config = config
    # Acquire the advisory lock before connecting and hold it for the lifetime of this handle.
    self._lock_fd:int|None = acquire_advisory_lock(config.lock_path, exclusive=exclusive, blocking=True,
      allow_group=config.lock_allow_group)

    try: # Release the lock on any failure during connection or validation; otherwise it would leak.
      mode:Mode = 'rw' if rw else 'ro'
      self.conn = _connect(config, mode=mode, trace_caller_level=trace_caller_level)

      try: # Close the conn if version validation fails; otherwise the conn would leak.
        c = self.conn.cursor()
        main_user_version:int = c.user_version()

        if main_user_version < config.user_version:
          logI('Database stored user_version is behind.', stored=main_user_version, static=config.user_version)
        elif main_user_version > config.user_version:
          logW('Database stored user_version is ahead.', stored=main_user_version, static=config.user_version)

        for name in config.names:
          stored = c.user_version(name)
          if stored != main_user_version:
            logW(f'Attached user_version is out of sync: {name}:{stored} < main:{main_user_version}.')
      except BaseException:
        self.conn.close()
        raise
    except BaseException:
      self._release_lock()
      raise


  @classmethod
  def ro(cls, config:DbConfig|None=None) -> Self:
    'Create a read-only database handle.'
    return cls(config, rw=False, trace_caller_level=4)


  @classmethod
  def rw(cls, config:DbConfig|None=None, *, exclusive:bool=False) -> Self:
    'Create a read-write database handle.'
    return cls(config, rw=True, exclusive=exclusive, trace_caller_level=4)


  @classmethod
  def initialize(cls, config:DbConfig|None=None) -> None:
    'Create and initialize each database file, setting WAL mode. Idempotent: safe to call on existing files.'
    config = config or cls.global_config()
    with config.exclusive_lock():
      for name, path in config.paths.items():
        logI('Initializing database.', name=name, path=path)
        with Conn(path, mode='rwc').closing() as conn:
          result = conn.run('PRAGMA journal_mode = WAL').one_col()
          if result != 'wal':
            raise Exception(f'Failed to set WAL mode on {path!r} (db: {name!r}); got {result!r}.')


  def _release_lock(self) -> None:
    'Release the held advisory lock, if any. Idempotent.'
    if self._lock_fd is not None:
      release_advisory_lock(self._lock_fd)
      self._lock_fd = None


  def close(self) -> None:
    'Close the connection and release the held advisory lock.'
    try:
      self.conn.close()
    finally:
      self._release_lock()


  def __enter__(self) -> Self:
    return self


  def __exit__(self, exc_type:object, exc_val:object, exc_tb:object) -> None:
    self.close()


  def backup_all(self, backup_dir:str) -> list[str]:
    return [self.backup_db(name=name, backup_dir=backup_dir) for name in self.config.names]


  def backup_db(self, name:str, backup_dir:str) -> str:
    '''
    Back up a single database file using VACUUM INTO.
    Produces a compacted copy whose underlying pages differ from the original.
    '''
    db_path = self.config.path(name)
    backup_path = path_join(backup_dir, f'{name}.db')
    if db_path == backup_path:
      raise ValueError(f'Backup path {backup_path!r} is the same as the database path {db_path!r}.')

    if path_exists(backup_path, follow=False):
      prev_path = backup_path + '.prev'
      logI('Backup database path already exists; moving to .prev.', backup_path=backup_path, prev_path=prev_path)
      move_file(path=backup_path, to=prev_path, overwrite=True)

    logI('Backing up database.', name=name)

    with Conn(db_path, mode='ro').closing() as src_conn:
      src_conn.run('VACUUM INTO :backup_path', backup_path=backup_path)

    with Conn(backup_path, mode='rw').closing() as backup_conn:
      backup_conn.cursor().run('PRAGMA journal_mode = WAL')

    size = file_size(backup_path)
    logI('Database backup complete.', name=name, backup_path=backup_path, size_bytes=format_byte_count(size))
    return backup_path


  def sync_db(self, name:str, sync_dir:str) -> str:
    '''
    Sync a database to a replica using sqlite3_rsync (transactional, page-by-page).
    Successive syncs are usually much faster than a full backup.
    '''
    db_path = self.config.path(name)
    sync_path = path_join(sync_dir, f'{name}.sync.db')
    if db_path == sync_path:
      raise ValueError(f'Sync path {sync_path!r} is the same as the database path {db_path!r}.')

    logI('Syncing database.', name=name, db_path=db_path, sync_path=sync_path)
    run(['sqlite3_rsync', db_path, sync_path])
    size = file_size(sync_path)
    logI('Database sync complete.', name=name, sync_path=sync_path, size_bytes=format_byte_count(size))
    return sync_path


  def truncate_wal(self, *names:str) -> None:
    'Run `wal_checkpoint(TRUNCATE)` to clean up -wal and -shm files for the named databases, or all if none are named.'
    names = names or self.config.names
    c = self.conn.cursor()
    for name in names:
      if name not in self.config.names:
        raise ValueError(f'Database.truncate_wal: unknown database name: {name!r}; known names: {self.config.names}.')
      c.run(f'PRAGMA {name}.wal_checkpoint(TRUNCATE)')


  def get_file_sizes(self) -> dict[str,int]:
    return {name: file_size(path) for name, path in self.config.paths.items()}


def set_all_user_versions(c:Cursor, names:Iterable[str], version:int) -> None:
  'Set the `user_version` pragma on each named database.'
  for name in names:
    c.set_user_version(name, version)


def _connect(config:DbConfig, *, mode:Mode, trace_caller_level:int) -> Conn:

  for name, path in config.paths.items():
    if not is_file(path, follow=True): exit(f'error: database file not found: {path!r} (db: {name!r}).')

  conn = Conn(config.paths[config.names[0]], mode=mode, check_same_thread=False,
    trace_caller_level=trace_caller_level)

  try: # Close the conn on any failure during setup.
    for name in config.names[1:]:
      path = config.path(name)
      try: conn.attach(path, name=name, mode=mode)
      except Exception as e:
        e.add_note(f'error: failed to attach database file: {path!r}.')
        raise

    c = conn.cursor()

    for name in config.names:
      journal_mode = c.run(f'PRAGMA {name}.journal_mode').one_col()
      if journal_mode != 'wal':
        raise Exception(
          f'Database {name!r} is not in WAL mode (found {journal_mode!r}); '
          f'use Database.initialize() to set up a new database.')

    if mode == 'ro': c.run('PRAGMA query_only = 1')

    c.run(f'PRAGMA cache_size = {-1024 * config.cache_mb}')

    if config.synchronous_full:
      c.run('PRAGMA synchronous = FULL')
    else:
      c.run('PRAGMA synchronous = NORMAL')

    c.run('PRAGMA temp_store = memory')

  except BaseException:
    conn.close()
    raise

  return conn
