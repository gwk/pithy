# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Backup and restore for a pithy.sqlite Database group.

The engine is storage-vendor-neutral: cloud object storage is injected via the `BackupStore` protocol.
See `inish.backblaze` for a Backblaze B2 implementation.

Application policy is injected via `BackupConfig` callables, so each hook can run arbitrary application code.
These include credential and bucket resolution, post-restore data mutations, file ownership normalization.

A backup pipeline run has two steps, each conditioned on the intervals in `BackupFileConfig`:
* produce a local artifact by one of two methods (sync or vacuum), per `sync_interval`;
* upload it, per `upload_interval`.

Both steps read the whole database, so their runtime/IO/network costs grow with file size.

Intervals are aligned to the clock rather than measured from the previous operation:
* an interval of 30m runs after the hour and half-hour;
* an interval of 1d runs after midnight, by the system timezone or by UTC per `BackupConfig.use_utc`;
* an interval of 7d runs after midnight on Sunday.

The grid is phased by standard time, so under daylight saving a daily upload happens after 01:00 local.
This results in at most one operation per elapsed interval, including across daylight saving transitions.

Local files are written to `BackupConfig.backups_dir`.
This can be a different volume than the data dir, so a local copy survives loss of the data mount.
Backup files:
* `{name}.db`: vacuum backup copy; a preexisting copy is first moved to `{name}.db.prev`.
* `{name}.sync.db`: sqlite3_rsync replica.
* `{artifact}.syncts`: timestamp of the last production of the adjacent artifact.
* `{artifact}.uploadts`: timestamp of the last upload of the adjacent artifact.
* `{name}.backuptrigger`: request that the next run sync and upload, whatever its intervals.

Restore artifacts are colocated with the canonical database files.
They are plain files, not coordinated by the Database advisory lock;
only the active database files are covered by the advisory lock logic.
* `{db_path}_{timestamp}.downloaded`: verified download of a cloud backup version, cached for reuse.
* `{db_path}.restoring`: working copy that is mutated and then moved into place.
'''

import time
from dataclasses import dataclass, field
from hashlib import sha1
from os import getpid
from typing import Callable, cast, get_args, Literal, Mapping, Protocol, Sequence

from ...argparser import CommandParser, Namespace
from ...date import DateTime, dt_Ymd_HMS, dt_Ymd_HMS_Z
from ...filestatus import StatResult
from ...fs import copy_path, file_size, file_stat, is_file, move_file, path_exists, remove_file_if_exists
from ...logs import logI
from ...signals import HoldSignals
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

default_key = '_' # Key naming the default entry in mappings that are otherwise keyed by database name.

backuptrigger_suffix = '.backuptrigger'
syncts_suffix = '.syncts'
uploadts_suffix = '.uploadts'
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
  * `files`: per-database `BackupFileConfig` entries.
    Each key must be a name in `db_config.names`, or the `default_key` '_', which applies to every unnamed database.
    Every database file must be covered by either a named entry or an explicit default.
  * `use_utc`: align the upload interval grid by UTC instead of by the server timezone.
  * `make_save_store`: read-write store factory for uploads; `None` disables uploads.
  * `make_restore_store`: read-only store factory for restores. The optional `store_name` is app-defined
    (e.g. a deployment stage); the factory validates it, including any safety guards on which stores a host may restore from.
  * `mutate_restored`: hook `(restoring_path, name)` applied to the `.restoring` copy before it is moved into place,
    e.g. to clear queued actions that a restored copy must not replay against live systems.
    The engine checkpoints the WAL and removes sidecar files after the hook runs; the hook need not do so.
  * `fix_data_file_perms`: ownership/permission normalization applied to every file the engine creates in the data dir.
  '''

  db_config: DbConfig
  backups_dir: str
  files: Mapping[str,BackupFileConfig]
  use_utc: bool = False
  make_save_store: Callable[[],BackupStore]|None = None
  make_restore_store: Callable[[str|None],BackupStore]|None = None
  mutate_restored: Callable[[str,str],None]|None = None
  fix_data_file_perms: Callable[[str],None] = lambda _: None

  def __post_init__(self) -> None:
    db_names = frozenset(self.db_config.names)
    if unknown := sorted(name for name in self.files if name not in db_names and name != default_key):
      raise ValueError(f'BackupConfig.files names unknown databases: {unknown}; '
        f'DbConfig.names are {self.db_config.names!r}.')
    # Without the default entry every database must be named, so that adding one to the group cannot silently omit it.
    if default_key not in self.files:
      if missing := sorted(name for name in self.db_config.names if name not in self.files):
        raise ValueError(f'BackupConfig.files has no default and missing entries: {missing}.')


@dataclass(frozen=True)
class BackupFileConfig:
  '''
  Backup configuration for a single database file.
  Each interval is a non-negative float in seconds or a timespan string like '15s'|'30m'|'1h'.

  * `sync_interval`: how often to produce the local artifact; `None` means never; `0` means every run.
  * `upload_interval`: how often to upload the local artifact; `None` means never; `0` means every run.
  '''

  sync_interval: float|str|None
  upload_interval: float|str|None
  _sync_interval_s: float|None = field(init=False, repr=False, compare=False)
  _upload_interval_s: float|None = field(init=False, repr=False, compare=False)

  def __post_init__(self) -> None:
    object.__setattr__(self, '_sync_interval_s',
      normalize_interval(self.sync_interval, desc='BackupFileConfig.sync_interval'))
    object.__setattr__(self, '_upload_interval_s',
      normalize_interval(self.upload_interval, desc='BackupFileConfig.upload_interval'))


def normalize_interval(interval:float|str|None, *, desc:str) -> float|None:
  'Normalize a configured interval to non-negative seconds, or `None`. `desc` names the field for errors.'
  if interval is None: return None
  seconds = parse_timespan_as_seconds(interval) if isinstance(interval, str) else interval
  if seconds < 0: raise ValueError(f'{desc} must be zero, positive, or None; received {interval!r}.')
  return seconds


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


def local_backup_path(config:BackupConfig, name:str, *, method:BackupMethod) -> str:
  'Path of the local backup artifact for a single database, as produced by `Database.backup_db`/`Database.sync_db`.'
  suffix = '.db' if method == 'vacuum' else '.sync.db'
  return f'{config.backups_dir}/{name}{suffix}'


def create_local_backup(config:BackupConfig, name:str, *, method:BackupMethod) -> str:
  'Produce a local backup artifact for a single database in `backups_dir` and return its path.'
  with Database.ro(config.db_config) as db:
    if method == 'vacuum':
      return db.backup_db(name=name, backup_dir=config.backups_dir)
    else:
      return db.sync_db(name=name, sync_dir=config.backups_dir)


def maybe_create_local_backup(config:BackupConfig, name:str, *, method:BackupMethod, interval:float|None, force:bool=False
 ) -> str:
  '''
  Conditionally produce a local backup for a single database; return its path regardless.
  Skip if the previous production as recorded by the adjacent `.syncts` file falls in the same interval slot as now.
  `interval` must be non-negative; `None` never produces (once an artifact exists); `0` produces on every call.
  `force` produces the artifact regardless of `interval` and the sidecar file, and still records the timestamp.

  A skipped production leaves the previous artifact in place, so an upload due in this run uploads that older copy.
  '''
  path = local_backup_path(config, name, method=method)
  syncts_path = path + syncts_suffix
  now = now_utc()

  # A missing artifact is always produced; the timestamp alone would otherwise gate a run that has nothing to upload.
  if not force and is_file(path, follow=True):
    if interval is None:
      return path
    if interval > 0 and not is_interval_elapsed(syncts_path, now=now, interval=interval, use_utc=config.use_utc):
      return path

  created_path = create_local_backup(config, name, method=method)
  assert created_path == path, (created_path, path)
  write_ts_file(syncts_path, now)
  return path


def maybe_upload(store:BackupStore, path:str, obj_key:str, *, interval:float|None, use_utc:bool=False,
 force:bool=False) -> bool:
  '''
  Conditionally upload `path` to `store` as `obj_key`;
  skip if the previous upload as recorded by the adjacent `.uploadts` file falls in the same interval slot as now.
  `interval` must be non-negative; `None` never uploads; `0` uploads on every call.
  `force` uploads regardless of `interval` and the sidecar file, and still records the timestamp.
  Returns True if an upload completed.
  '''
  uploadts_path = path + uploadts_suffix
  now = now_utc()

  if not force:
    if interval is None: return False
    if interval > 0 and not is_interval_elapsed(uploadts_path, now=now, interval=interval, use_utc=use_utc): return False

  logI('Uploading to store.', store=store.name, path=path, obj_key=obj_key)
  if not store.upload(path, obj_key):
    logI('Upload did not complete.', store=store.name, obj_key=obj_key)
    return False

  logI('Upload complete; timestamp written.', uploadts_path=uploadts_path, ts=write_ts_file(uploadts_path, now))
  return True


def is_interval_elapsed(ts_path:str, *, now:DateTime, interval:float, use_utc:bool) -> bool:
  '''
  True if the timestamp sidecar file at `ts_path` is missing, or records a time in an earlier interval slot than `now`.
  A missing file means the operation has never run, which counts as elapsed.
  '''
  slot = interval_slot(now, interval=interval, use_utc=use_utc) # Computed first, so that a bad interval always raises.
  if not is_file(ts_path, follow=True): return True
  with open(ts_path) as f:
    prev_ts = DateTime.fromisoformat(f.read().strip())
  return interval_slot(prev_ts, interval=interval, use_utc=use_utc) != slot


def write_ts_file(ts_path:str, dt:DateTime) -> str:
  'Record `dt` in the timestamp sidecar file at `ts_path` and return the formatted timestamp.'
  ts = dt_Ymd_HMS_Z(dt)
  with open(ts_path, 'w') as f:
    print(ts, file=f)
  return ts


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


def trigger_file_path(config:BackupConfig, name:str) -> str:
  'Path of the marker file that triggers an upload of `name` on the next backup run.'
  return f'{config.backups_dir}/{name}{backuptrigger_suffix}'


def write_trigger_file(config:BackupConfig, name:str) -> str:
  '''
  Write the marker file corresponding to `name` to trigger an upload. Returns the file path.

  The marker is written to a temporary path and renamed into place, so it appears atomically and every request is a
  distinct file. A request made while a run is in flight therefore survives that run and is honored by the next one,
  which is correct: the artifact that run uploads was produced before the request was made.

  Only the marker's existence is meaningful; the contents are informational.
  Note that the writer need not be the user that the backup service runs as, because creating and removing the marker requires
  write permission on the backups dir, not on the marker itself.
  '''
  path = trigger_file_path(config, name)
  tmp_path = f'{path}.{getpid()}.tmp' # Distinct per process, so that concurrent writers cannot share a temporary file.
  with open(tmp_path, 'w') as f:
    print(dt_Ymd_HMS_Z(now_utc()), file=f)
  move_file(tmp_path, to=path, overwrite=True)
  return path


def stat_trigger_file(config:BackupConfig, name:str) -> StatResult|None:
  '''
  Stat the trigger marker for `name`, returning None if no upload was requested.
  The result identifies the particular request, and is passed back to `clear_trigger_file` once it has been satisfied.

  A run claims a trigger by stat'ing it, and must do so before it produces the local artifact,
  so that the artifact it uploads is at least as new as the request it satisfies.
  It must also clear the trigger only after the upload succeeds,
  so that a failed or interrupted run leaves the request for the next one.
  '''
  try: return file_stat(trigger_file_path(config, name), follow=True)
  except FileNotFoundError: return None


def clear_trigger_file(config:BackupConfig, name:str, claimed:StatResult) -> None:
  '''
  Remove the trigger marker for `name`.
  A marker rewritten since it was claimed is a second request, so it is left in place for the next run.
  '''
  path = trigger_file_path(config, name)
  try: current = file_stat(path, follow=True)
  except FileNotFoundError: return # Already removed, e.g. by a concurrent run.
  if (current.st_ino, current.st_mtime_ns) != (claimed.st_ino, claimed.st_mtime_ns):
    logI('Leaving the backup trigger in place; it was rewritten during this run.', path=path)
    return
  remove_file_if_exists(path)
  logI('Backup trigger cleared.', path=path)


def backup_and_upload(config:BackupConfig, names:Sequence[str], *, method:BackupMethod, should_stop:Callable[[],bool]|None=None
 ) -> None:
  '''
  For each named database, conditionally produce a local backup artifact, then conditionally upload it.
  The BackupFileConfig time intervals dictate whether each step is taken.
  A database with a pending trigger marker file is produced and uploaded regardless of the intervals, including `None` (never).
  `should_stop` is polled before each database is processed,
  so that a stop request takes effect between databases instead of interrupting a sync or upload.
  '''
  file_configs = {name: file_config_for(config, name) for name in names}
  # Test for the markers up front, because a database whose interval is None still needs the store if it has been triggered.
  # This is only a test; each marker is claimed in the loop below, so that a request arriving during the run is not missed.
  triggered = {name for name in names if is_file(trigger_file_path(config, name), follow=True)}

  store:BackupStore|None = None
  if any(file_configs[name]._upload_interval_s is not None or name in triggered for name in names):
    if config.make_save_store is None: exit('error: backup config has no save store factory; cannot upload.')
    store = config.make_save_store()

  for name in names:
    if should_stop is not None and should_stop():
      logI('Stop requested.')
      return
    file_config = file_configs[name]
    interval = file_config._upload_interval_s
    # Claim the trigger before producing the artifact, so that the artifact is at least as new as the request it satisfies.
    # A trigger also forces production, for the same reason.
    claimed = stat_trigger_file(config, name)
    path = maybe_create_local_backup(config, name, method=method, interval=file_config._sync_interval_s,
      force=claimed is not None)
    if store is None: continue
    if claimed is None:
      maybe_upload(store, path, obj_key=f'{name}.db', interval=interval, use_utc=config.use_utc)
    else:
      logI('Backup trigger found.', name=name, path=trigger_file_path(config, name))
      if maybe_upload(store, path, obj_key=f'{name}.db', interval=interval, use_utc=config.use_utc, force=True):
        clear_trigger_file(config, name, claimed)


def file_config_for(config:BackupConfig, name:str) -> BackupFileConfig:
  'Resolve the config for a single database: its own entry, else the `default_key` entry.'
  files = config.files
  if (file_config := files.get(name)) is not None: return file_config
  return files[default_key] # BackupConfig validates that every database is covered by an entry or the default.


def sync_interval_for(config:BackupConfig, name:str) -> float|None:
  'Resolve the sync interval in seconds for a single database; `None` means never produce an artifact.'
  return file_config_for(config, name)._sync_interval_s


def upload_interval_for(config:BackupConfig, name:str) -> float|None:
  'Resolve the upload interval in seconds for a single database; `None` means never upload.'
  return file_config_for(config, name)._upload_interval_s


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

  dl_path = f'{db_path}.{store.name}_{latest.uploaded_at:%Y-%m-%d_%H_%M}{downloaded_suffix}'

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
  remove_wal_shm(restoring_path) # Clear any sidecar files left by a prior interrupted run before copying over the file.
  logI('Copying backup to the .restoring path.', from_path=dl_path, to_path=restoring_path)
  copy_path(dl_path, dst=restoring_path, follow=True, preserve_meta=True)

  finalize_restoring_db(config, restoring_path, name=name)

  # Remove any stale -wal/-shm sidecar files from the canonical path before moving the file in; otherwise SQLite would
  # replay the old WAL onto the restored database and corrupt it.
  remove_wal_shm(db_path)

  logI('Moving the .restoring database into place.', from_path=restoring_path, to_path=db_path)
  move_file(restoring_path, to=db_path, overwrite=True)

  # The copy and move above do not carry ownership, so normalize the canonical file.
  config.fix_data_file_perms(db_path)

  return True


def finalize_restoring_db(config:BackupConfig, restoring_path:str, *, name:str) -> None:
  '''
  Apply the app mutation hook to the `.restoring` copy, then checkpoint the WAL and remove sidecar files,
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

  trigger_cmd = parser.add_command(main_trigger)
  if with_app_arg: trigger_cmd.add_argument('app', help=app_spec_help)
  trigger_cmd.add_argument('names', nargs='+', help='Names of databases to request an upload for, or "all".')

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
  # SIGTERM is held so that a stop request lands between databases rather than mid-write; see `backup_and_upload`.
  # HoldSignals delivers the signal when the block exits, so the process still terminates by it.
  with HoldSignals() as hold_signals:
    backup_and_upload(config, names, method=args.method, should_stop=hold_signals.is_signal_on_hold)


def main_trigger(args:Namespace) -> None:
  '''
  Request that the next backup run upload the named databases, whatever their configured upload intervals.
  This only requests an upload; it does not perform one.
  '''
  config = config_for_args(args)
  names = parse_db_names(args.names, config=config.db_config)
  for name in names:
    logI('Backup trigger written.', path=write_trigger_file(config, name))


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
