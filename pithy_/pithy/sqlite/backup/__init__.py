# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Backup and restore for a pithy.sqlite Database group.

The engine is storage-vendor-neutral: cloud object storage is injected via the `BackupStore` protocol.
See `inish.backblaze` for a Backblaze B2 implementation.

Application policy is injected via `BackupConfig` callables, so each hook can run arbitrary application code.
These include credential and bucket resolution, post-restore data mutations, file ownership normalization.

A backup pipeline run has two steps:
* produce a local artifact by one of two methods (sync or vacuum);
* maybe upload it depending on the configured time interval.

Upload intervals are aligned to the clock rather than measured from the previous upload:
* an interval of 30m uploads after the hour and half-hour;
* an interval of 1d uploads after midnight, by the system timezone or by UTC per `BackupConfig.use_utc`;
* an interval of 7d uploads after midnight on Sunday.

The grid is phased by standard time, so under daylight saving a daily upload happens after 01:00 local.
This results in at most one upload per elapsed interval, including across daylight saving transitions.

Local files are written to `BackupConfig.backups_dir`.
This can be a different volume than the data dir, so a local copy survives loss of the data mount.
Backup files:
* `{name}.db`: vacuum backup copy; a preexisting copy is first moved to `{name}.db.prev`.
* `{name}.sync.db`: sqlite3_rsync replica.
* `{artifact}.cloudts`: timestamp of the last upload of the adjacent artifact.

Restore artifacts are colocated with the canonical database files.
They are plain files, not coordinated by the Database advisory lock;
only the active database files are covered by the advisory lock logic.
* `{db_path}_{timestamp}.downloaded`: verified download of a cloud backup version, cached for reuse.
* `{db_path}.restoring`: working copy that is mutated and then moved into place.
'''

import time
from argparse import SUPPRESS
from dataclasses import dataclass
from hashlib import sha1
from typing import Callable, cast, get_args, Literal, Protocol, Sequence

from ...argparser import CommandParser, Namespace
from ...date import DateTime, dt_Ymd_HMS, dt_Ymd_HMS_Z
from ...fs import copy_path, file_size, is_file, move_file, path_exists, remove_file_if_exists
from ...logs import logI
from ...sqlite import Conn
from ...strings import format_byte_count
from ...timespans import parse_timespan_as_seconds
from ...tz import now_utc
from ...util import resolve_module_spec
from ..database import Database, DbConfig


type BackupMethod = Literal['sync','vacuum']

backup_methods:tuple[BackupMethod,...] = get_args(BackupMethod.__value__)


grid_anchor_offset = 4 * 24 * 60 * 60.0
#^ The unix epoch began on a Thursday; we anchor our grid to the preceding Sunday to make weekly jobs happen Sunday at 00:00.

cloudts_suffix = '.cloudts'
downloaded_suffix = '.downloaded'
restoring_suffix = '.restoring'


@dataclass(frozen=True)
class StoredVersion:
  'One version of a backup object in a store, as reported by `BackupStore.list_versions`.'
  key: str            # Provider-specific version identifier, passed back to `BackupStore.download`.
  obj_key: str        # The object key (name) within the store.
  size: int           # Size in bytes.
  sha1: str|None      # Content SHA1 hex digest, if the provider records one; required for restore verification.
  uploaded_at: DateTime


class BackupStore(Protocol):
  '''
  Protocol for a versioned cloud object store holding database backups.
  Implementations own credentials, transport, and progress display.
  `upload` and `download` return False if the operation was deliberately interrupted (e.g. by the user);
  they raise for unexpected errors.

  * `name`: store name for logging, e.g. the bucket name.
  '''

  name:str

  def upload(self, path:str, obj_key:str) -> bool: ...

  def list_versions(self, obj_key:str) -> list[StoredVersion]: ...

  def download(self, version:StoredVersion, dst_path:str) -> bool: ...


type ConfigSource = BackupConfig|Callable[[],'BackupConfig']|str


@dataclass(frozen=True)
class BackupConfig:
  '''
  Configuration for backing up and restoring a Database group.
  The callable fields are application code; the engine only invokes them.

  * `backups_dir`: destination for local backup artifacts.
  * `upload_interval`: a float in seconds, or a timespan string like '15s'|'30m'|'1h'|'never', or `None` (never).
  * `use_utc`: phase the upload interval grid by UTC instead of by the system timezone.
  * `make_save_store`: read-write store factory for uploads; `None` disables uploads.
  * `make_restore_store`: read-only store factory for restores. The optional `store_name` is app-defined
    (e.g. a deployment stage); the factory validates it, including any safety guards on which stores a host may restore from.
  * `mutate_restored`: hook `(restoring_path, name)` applied to the `.restoring` copy before it is moved into place,
    e.g. to clear queued actions that a restored copy must not replay against live systems.
    The engine checkpoints the WAL and removes sidecars after the hook runs; the hook need not do so.
  * `fix_data_file_perms`: ownership/permission normalization applied to every file the engine creates in the data dir.
  '''

  db_config: DbConfig
  backups_dir: str
  upload_interval: float|str|None
  use_utc: bool = False
  make_save_store: Callable[[],BackupStore]|None = None
  make_restore_store: Callable[[str|None],BackupStore]|None = None
  mutate_restored: Callable[[str,str],None]|None = None
  fix_data_file_perms: Callable[[str],None] = lambda _: None
  _upload_interval_s: float|None = None

  def __post_init__(self) -> None:
    interval = self.upload_interval
    if isinstance(interval, str):
      interval = parse_upload_interval(interval)
    if interval is not None and interval <= 0:
      raise ValueError(f'BackupConfig.upload_interval must be positive or None; received {interval!r}.')
    object.__setattr__(self, '_upload_interval_s', interval)


def parse_upload_interval(value:str) -> float|None:
  'Parse an upload interval string: "never" -> None, otherwise a positive timespan converted to seconds.'
  if value == 'never': return None
  interval = parse_timespan_as_seconds(value)
  if interval <= 0: raise ValueError(f'upload interval must be positive or "never"; received {value!r}.')
  return interval


def resolve_backup_config(source:ConfigSource) -> BackupConfig:
  '''
  Resolve a BackupConfig from a config, a zero-argument factory callable, or a `module[:attr]` spec string.

  A spec string module is imported by its full dotted path, so the application package initializes normally
  and the config's hooks can rely on any application code.
  The default attribute is `load_backup_config`; the resolved attribute may be a BackupConfig or a factory.
  '''
  obj:object = resolve_module_spec(source, default_attr='load_backup_config') if isinstance(source, str) else source
  if isinstance(obj, BackupConfig): return obj
  if callable(obj):
    config = obj()
    if isinstance(config, BackupConfig): return config
    exit(f'error: backup config source {source!r} returned {type(config).__name__}, not a BackupConfig.')
  exit(f'error: backup config source {source!r} resolved to {type(obj).__name__}, '
    'which is not a BackupConfig or a callable returning one.')


def create_local_backup(config:BackupConfig, name:str, *, method:BackupMethod) -> str:
  'Produce a local backup artifact for a single database in `backups_dir` and return its path.'
  with Database.ro(config.db_config) as db:
    if method == 'vacuum':
      return db.backup_db(name=name, backup_dir=config.backups_dir)
    else:
      return db.sync_db(name=name, sync_dir=config.backups_dir)


def maybe_upload(store:BackupStore, path:str, obj_key:str, *, interval:float|None, use_utc:bool=False) -> bool:
  '''
  Conditionally upload `path` to `store` as `obj_key`;
  skip if the previous upload as recorded by the adjacent `.cloudts` file falls in the same interval slot as now.
  `interval` must be positive; `None` never uploads.
  Returns True if an upload completed.
  '''
  if interval is None: return False

  cloudts_path = path + cloudts_suffix
  now = now_utc()
  slot = interval_slot(now, interval=interval, use_utc=use_utc)

  if is_file(cloudts_path, follow=True):
    with open(cloudts_path) as f:
      prev_ts_str = f.read().strip()
    prev_ts = DateTime.fromisoformat(prev_ts_str)
    if interval_slot(prev_ts, interval=interval, use_utc=use_utc) == slot:
      return False

  logI('Uploading to store.', store=store.name, path=path, obj_key=obj_key)
  if not store.upload(path, obj_key):
    logI('Upload did not complete.', store=store.name, obj_key=obj_key)
    return False

  now_ts = dt_Ymd_HMS_Z(now)
  with open(cloudts_path, 'w') as f:
    print(now_ts, file=f)
  logI('Upload complete; timestamp written.', cloudts_path=cloudts_path, ts=now_ts)
  return True


def interval_slot(dt:DateTime, *, interval:float, use_utc:bool) -> int:
  '''
  Identify the time slot of length `interval` seconds that contains `dt`.
  Slots tile the timeline end to end, so consecutive slots are exactly `interval` apart in elapsed time.

  The grid is anchored at `grid_anchor_offset` before the epoch, phased by UTC if `use_utc`,
  otherwise by the system timezone.
  An interval that divides the day evenly aligns to the clock: 1h begins on the hour, 1d at midnight.
  Any other interval is equally periodic but its boundaries precess through the day;
  a whole number of days also begins at midnight, on dates fixed by the anchor, e.g. 7d falls on Sundays.

  `interval` must be positive.

  The system time "phase" is always the standard-time (non-daylight-saving) offset, not the offset in effect at `dt`.
  This way daylight saving does not perturb the grid:
  * spring forward skips no slot;
  * the repeated hour of the fall back is two slots rather than one.
  Since the grid does not move, daylight saving relabels the boundaries an hour later on the local clock:
  a daily slot begins at 01:00 local rather than midnight. An interval that divides an hour evenly is unchanged.
  '''
  if interval <= 0: raise ValueError(f'interval must be positive; received {interval!r} seconds.')
  std_offset = 0.0 if use_utc else -float(time.timezone)
  #^ `time.timezone` is the standard-time offset in seconds west of UTC, so it does not change across a DST transition.
  #^ It does change when tzset() is called, so we access it through the module.
  return int((dt.timestamp() + std_offset + grid_anchor_offset) // interval)


def backup_and_upload(config:BackupConfig, names:Sequence[str], *, method:BackupMethod, upload_interval:float|None) -> None:
  'Produce a local backup artifact for each named database, then conditionally upload each, depending on `upload_interval`.'

  store:BackupStore|None = None
  if upload_interval is not None:
    if config.make_save_store is None: exit('error: backup config has no save store factory; cannot upload.')
    store = config.make_save_store()

  for name in names:
    path = create_local_backup(config, name, method=method)
    if store is not None:
      maybe_upload(store, path, obj_key=f'{name}.db', interval=upload_interval, use_utc=config.use_utc)


def restore_all(config:BackupConfig, names:Sequence[str], *, store_name:str|None=None) -> None:
  'Restore each named database from the store selected by `store_name`, holding the exclusive group lock throughout.'

  if config.make_restore_store is None: exit('error: backup config has no restore store factory; cannot restore.')
  store = config.make_restore_store(store_name)

  db_config = config.db_config
  # Restore replaces the database files directly, so hold the exclusive group lock for the whole operation;
  # all other participants block until it completes.
  with db_config.exclusive_lock():
    for name in names:
      if not restore_db(config, store, name): exit(1)
    # The manifest is not part of the backup, so write it here for discovery by generic tools.
    db_config.write_manifest()
    config.fix_data_file_perms(db_config.manifest_path)


def restore_db(config:BackupConfig, store:BackupStore, name:str) -> bool:
  '''
  Restore a single database from the latest version in `store`.
  The caller must hold the exclusive group lock: the canonical database file is replaced directly.
  '''
  db_path = config.db_config.path(name)
  obj_key = f'{name}.db'

  logI('restore:', store=store.name, obj_key=obj_key)

  versions = store.list_versions(obj_key)
  if not versions:
    logI('No backup found.', store=store.name, obj_key=obj_key)
    return False

  versions.sort(key=lambda v: v.uploaded_at)

  lv = len(versions)
  if lv > 1:
    log_stored_version('prev', idx=lv-2, version=versions[lv-2])

  latest = versions[-1]
  log_stored_version('last', idx=lv-1, version=latest)

  if not latest.sha1:
    logI('Latest backup version has no SHA1; cannot verify a download.', obj_key=obj_key, key=latest.key)
    return False

  dl_path = f'{db_path}_{latest.uploaded_at:%Y%m%d_%H%M}{downloaded_suffix}'

  if path_exists(dl_path, follow=False):
    existing_size = file_size(dl_path)
    if existing_size != latest.size:
      logI('Download path already exists but file size does not match; please remove this file.', path=dl_path,
        existing_size=existing_size, expected_size=latest.size)
      return False
    existing_sha1 = sha1_for_file(dl_path)
    if existing_sha1 != latest.sha1:
      logI('Download path already exists but SHA1 does not match; please remove this file.', path=dl_path,
        existing_sha1=existing_sha1, expected_sha1=latest.sha1)
      return False

    logI('Download path already exists; not downloading.', path=dl_path)

  else:
    logI('Downloading latest backup.', path=dl_path, key=latest.key)
    if not store.download(latest, dl_path):
      remove_file_if_exists(dl_path) # Do not leave a partial download to confuse the next attempt.
      return False
    # Normalize ownership at the point of creation, so every artifact in the data dir has canonical ownership.
    config.fix_data_file_perms(dl_path)

  # Perform the restore mutations on a non-canonical `.restoring` copy, then move it into place. This keeps the pristine
  # download at `dl_path` (which may be reused) untouched, and never exposes a half-mutated database file.
  restoring_path = db_path + restoring_suffix
  remove_wal_shm(restoring_path) # Clear any sidecars left by a prior interrupted run before copying over the file.
  logI('Copying backup to the .restoring path.', from_path=dl_path, to_path=restoring_path)
  copy_path(dl_path, dst=restoring_path, follow=True, preserve_meta=True)

  finalize_restoring_db(config, restoring_path, name=name)

  # Remove any stale -wal/-shm sidecars from the canonical path before moving the file in; otherwise SQLite would
  # replay the old WAL onto the restored database and corrupt it.
  remove_wal_shm(db_path)

  logI('Moving the .restoring database into place.', from_path=restoring_path, to_path=db_path)
  move_file(restoring_path, to=db_path, overwrite=True)

  # The copy and move above do not carry ownership, so normalize the canonical file.
  config.fix_data_file_perms(db_path)

  return True


def finalize_restoring_db(config:BackupConfig, restoring_path:str, *, name:str) -> None:
  '''
  Apply the app mutation hook to the `.restoring` copy, then checkpoint the WAL and remove sidecars,
  so the restoring file is a standalone database that can be moved alone.
  '''
  if config.mutate_restored is not None:
    config.mutate_restored(restoring_path, name)
  with Conn(restoring_path, mode='rw').closing() as conn:
    conn.cursor().run('PRAGMA wal_checkpoint(TRUNCATE)')
  remove_wal_shm(restoring_path)


def remove_wal_shm(db_path:str) -> None:
  'Remove the -wal and -shm sidecar files for the SQLite database at `db_path`, if present.'
  for suffix in ('-wal', '-shm'):
    remove_file_if_exists(db_path + suffix)


def parse_db_names(names:Sequence[str], *, config:DbConfig) -> tuple[str,...]:
  'Validate database names against the config; "all" expands to every name in the group.'
  if 'all' in names:
    if len(names) > 1:
      exit('error: cannot specify "all" along with other database names.')
    return config.names
  for name in names:
    if name not in config.names:
      exit(f'error: invalid database name: {name!r}. Valid names are: {config.names!r} or "all".')
  return tuple(names)


def sha1_for_file(path:str) -> str:
  hasher = sha1()
  with open(path, 'rb') as f:
    while chunk := f.read(1<<14): # 16k chunks.
      hasher.update(chunk)
  return hasher.hexdigest()


def log_stored_version(msg:str, *, idx:int, version:StoredVersion) -> None:
  logI(msg, obj_key=version.obj_key, idx=idx, uploaded_at=dt_Ymd_HMS(version.uploaded_at),
    size=format_byte_count(version.size), sha1=version.sha1, key=version.key)


# CLI.


def main_entry(config_source:ConfigSource|None=None, *, prog:str|None=None) -> None:
  '''
  Run the backup CLI. Applications can call this with their own config source or use `python -m pithy.sqlite.backup`.
  If `config_source` is None, each command takes an `app` module-spec positional argument instead
  (the form used by `python3 -m pithy.sqlite.backup`); see `resolve_backup_config`.
  '''
  parser = CommandParser(prog=prog, description='Backup and restore a pithy.sqlite Database group.')
  parser.set_defaults(config_source=config_source)
  with_app_arg = config_source is None

  save_cmd = parser.add_command(main_save)

  if with_app_arg: save_cmd.add_argument('app', help=app_spec_help)

  save_cmd.add_argument('names', nargs='+', help='Names of databases to back up, or "all".')
  save_cmd.add_argument('-method', choices=backup_methods, default='sync',
    help='Artifact production method: "sync" uses sqlite3_rsync (fast successive replication); '
      '"vacuum" uses VACUUM INTO (compacted copy).')

  # `None` means "never" so the default is set to SUPPRESS.
  save_cmd.add_argument('-upload-interval', type=parse_upload_interval, default=SUPPRESS, metavar='TIMESPAN|never',
    help='Specify the timespan for uploads, e.g. 1h, 30m, 30s. The timespan must be positive. '
      '"never" disables upload. Defaults to the config `upload_interval`.')

  restore_cmd = parser.add_command(main_restore)
  if with_app_arg: restore_cmd.add_argument('app', help=app_spec_help)
  restore_cmd.add_argument('-store', default=None,
    help='Backup store label passed to the restore store factory; app-defined, e.g. a deployment stage.')
  restore_cmd.add_argument('names', nargs='+', help='Names of databases to restore, or "all".')

  parser.parse_and_run_command()


app_spec_help = ('Dotted name of the application module that defines the backup config, '
  "optionally with a ':attribute' suffix (default attribute: 'load_backup_config'). See `resolve_backup_config`.")


def main_save(args:Namespace) -> None:
  'Produce local backup artifacts, optionally uploading them to cloud storage.'
  config = config_for_args(args)
  names = parse_db_names(args.names, config=config.db_config)
  if 'upload_interval' in args:
    upload_interval = args.upload_interval
  else:
    upload_interval = config._upload_interval_s
  backup_and_upload(config, names, method=args.method, upload_interval=upload_interval)


def main_restore(args:Namespace) -> None:
  'Restore databases from the cloud backup store, replacing the canonical database files.'
  config = config_for_args(args)
  names = parse_db_names(args.names, config=config.db_config)
  restore_all(config, names, store_name=args.store)


def config_for_args(args:Namespace) -> BackupConfig:
  source:ConfigSource|None = args.config_source
  if source is None:
    source = cast(str, args.app)
  return resolve_backup_config(source)
