# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import replace
from hashlib import sha1
from os import environ
from shutil import which
from tempfile import mkdtemp
from time import sleep, tzset

from pithy.date import DateTime, TimeDelta
from pithy.fs import is_file, path_exists, remove_file_if_exists
from pithy.logs import adjust_log_level
from pithy.sqlite import Conn
from pithy.sqlite.backup import (backup_and_upload, BackupConfig, BackupFileConfig, clear_trigger_file, create_local_backup,
  downloaded_suffix, interval_slot, maybe_upload, parse_db_names, parse_upload_interval, restore_db, stat_trigger_file,
  StoredVersion, upload_interval_for, uploadts_suffix, write_trigger_file)
from pithy.sqlite.database import Database, DbConfig
from pithy.tz import now_utc
from utest import utest, utest_exc, utest_val, utest_val_ne


class FakeStore:
  'In-memory BackupStore implementation for testing.'

  def __init__(self) -> None:
    self.name = 'fake'
    self.versions:dict[str,list[StoredVersion]] = {}
    self.contents:dict[str,bytes] = {}
    self.download_count = 0

  def upload(self, path:str, obj_key:str) -> bool:
    with open(path, 'rb') as f:
      data = f.read()
    key = f'{obj_key}#{len(self.versions.setdefault(obj_key, []))}'
    version = StoredVersion(key=key, obj_key=obj_key, size=len(data), sha1=sha1(data).hexdigest(), uploaded_at=now_utc())
    self.versions[obj_key].append(version)
    self.contents[key] = data
    return True

  def list_versions(self, obj_key:str) -> list[StoredVersion]:
    return list(self.versions.get(obj_key, ()))

  def download(self, version:StoredVersion, dst_path:str) -> bool:
    self.download_count += 1
    with open(dst_path, 'wb') as f:
      f.write(self.contents[version.key])
    return True


def read_rows(path:str) -> list[str]:
  with Conn(path, mode='ro').closing() as conn:
    return [row[0] for row in conn.run('SELECT x FROM T ORDER BY x')]


# Interval flag parsing.
utest(None, parse_upload_interval, 'never')
utest(1800.0, parse_upload_interval, '30m')
utest_exc(ValueError, parse_upload_interval, 'bogus')
utest_exc(ValueError, parse_upload_interval, '0s')
utest_exc(ValueError, parse_upload_interval, '-1h')


# Interval slots.

# The system timezone is used by default; force it to US/Pacific to test the DST behavior.
environ['TZ'] = 'US/Pacific'
tzset()

hour = 3600.0
day = 24 * hour


def slot(dt_str:str, *, interval:float, use_utc:bool=False) -> int:
  'Compute the interval slot of an ISO datetime string.'
  return interval_slot(DateTime.fromisoformat(dt_str), interval=interval, use_utc=use_utc)


def slots_from(dt_str:str, *, count:int, step:TimeDelta, interval:float, use_utc:bool=False) -> list[int]:
  'Compute the slots of `count` instants spaced `step` apart in elapsed time, starting at ISO datetime `dt_str`.'
  start = DateTime.fromisoformat(dt_str)
  return [interval_slot(start + step*i, interval=interval, use_utc=use_utc) for i in range(count)]


# Slots tile the timeline: instants less than one interval apart share a slot, and the next interval is the next slot.
utest_val(slot('2026-03-01T13:00:00+00:00', interval=hour), slot('2026-03-01T13:59:59+00:00', interval=hour),
  'one hour is one slot')
utest_val(slot('2026-03-01T13:00:00+00:00', interval=hour) + 1, slot('2026-03-01T14:00:00+00:00', interval=hour),
  'the next hour is the next slot')
utest_val(slot('2026-03-01T13:30:00+00:00', interval=day, use_utc=True), slot('2026-03-01T23:59:59+00:00', interval=day,
  use_utc=True), 'one UTC day is one slot')
utest_val(slot('2026-03-01T13:30:00+00:00', interval=day, use_utc=True) + 1,
  slot('2026-03-02T00:00:00+00:00', interval=day, use_utc=True), 'UTC daily slots begin at UTC midnight')

# The time grid is offset by the system timezone's notion of standard-time.
# The phase does not move under daylight saving, so it holds on both transition days and in between.
for date_str in ('2026-03-08', '2026-07-01', '2026-11-01'):
  utest_val(slot(f'{date_str}T07:59:59+00:00', interval=day) + 1, slot(f'{date_str}T08:00:00+00:00', interval=day),
    f'{date_str}: the daily slot begins at 00:00 PST (08:00 UTC)')

# Every elapsed hour is its own slot across both daylight saving transitions:
# the spring forward skips none of the 23 hours of its local day, and the fall back merges none of the 25 of its own.
spring_hourly = slots_from('2026-03-08T00:00:00-08:00', count=23, step=TimeDelta(hours=1), interval=hour)
utest_val(list(range(spring_hourly[0], spring_hourly[0]+23)), spring_hourly,
  'spring forward: 23 elapsed hours are 23 consecutive slots')

fall_hourly = slots_from('2026-11-01T00:00:00-07:00', count=25, step=TimeDelta(hours=1), interval=hour)
utest_val(list(range(fall_hourly[0], fall_hourly[0]+25)), fall_hourly,
  'fall back: 25 elapsed hours are 25 consecutive slots')

# A daily interval likewise advances by exactly one slot per 24 elapsed hours across either transition,
# so a 23-hour local day and a 25-hour one each still upload once.
for transition_date, offset in (('2026-03-08', '-08:00'), ('2026-11-01', '-07:00')):
  daily = slots_from(f'{transition_date}T00:00:00{offset}', count=3, step=TimeDelta(days=1), interval=day)
  utest_val(list(range(daily[0], daily[0]+3)), daily, f'{transition_date}: daily slots across the transition')

# An interval longer than a day is equally periodic; the grid is anchored to the Sunday preceding the epoch,
# so Pacific weekly slots begin at 00:00 PST on Sundays. The anchor offset is a whole number of days,
# so it does not disturb the daily and hourly positions asserted above.
utest_val(slot('2026-01-03T23:59:59-08:00', interval=7*day) + 1, slot('2026-01-04T00:00:00-08:00', interval=7*day),
  'weekly slots begin at 00:00 PST on Sunday')
weekly = slots_from('2026-01-04T00:00:00-08:00', count=4, step=TimeDelta(days=7), interval=7*day)
utest_val(list(range(weekly[0], weekly[0]+4)), weekly, 'weekly slots advance by one per 7 elapsed days')

# The standard-time phase holds for multi-day intervals too, so under daylight saving the boundary is 01:00 local.
utest_val(slot('2026-03-15T00:59:59-07:00', interval=7*day) + 1, slot('2026-03-15T01:00:00-07:00', interval=7*day),
  'a weekly slot under daylight saving begins at 01:00 PDT (00:00 PST)')

# An interval must be positive.
utest_exc(ValueError, slot, '2026-03-01T00:00:00+00:00', interval=0.0)
utest_exc(ValueError, slot, '2026-03-01T00:00:00+00:00', interval=-hour)


with adjust_log_level('warn'): # Silence the info-level logging that the backup engine emits for each operation.

  # Set up a database group with one table and a row.
  data_dir = mkdtemp(prefix='backup_ut_data')
  backups_dir = mkdtemp(prefix='backup_ut_backups')
  db_config = DbConfig(names=('main',), data_dir=data_dir)
  Database.initialize(db_config)

  with Database.rw(db_config) as db:
    c = db.conn.cursor()
    c.run('CREATE TABLE T (x TEXT)')
    c.run("INSERT INTO T VALUES ('original')")


  # Name validation.
  utest(('main',), parse_db_names, ['main'], config=db_config)
  utest(('main',), parse_db_names, ['all'], config=db_config)
  utest_exc(SystemExit, parse_db_names, ['bogus'], config=db_config)
  utest_exc(SystemExit, parse_db_names, ['all', 'main'], config=db_config)


  # Vacuum backup produces an artifact in the backups dir.
  store = FakeStore()
  mutated_names:list[str] = []
  fixed_up_paths:list[str] = []

  def mutate_restored(path:str, name:str) -> None:
    mutated_names.append(name)
    with Conn(path, mode='rw').closing() as conn:
      conn.cursor().run("INSERT INTO T VALUES ('mutated')")

  backup_config = BackupConfig(db_config=db_config, backups_dir=backups_dir,
    files=dict(_=BackupFileConfig(upload_interval=hour)),
    make_save_store=lambda: store, make_restore_store=lambda source: store, mutate_restored=mutate_restored,
    fix_data_file_perms=fixed_up_paths.append)

  def config_interval_s(upload_interval:float|str|None) -> float|None:
    'Construct a config whose default interval is `upload_interval` and return the interval resolved for "main".'
    config = BackupConfig(db_config=db_config, backups_dir=backups_dir,
      files=dict(_=BackupFileConfig(upload_interval=upload_interval)))
    return upload_interval_for(config, 'main')

  # The configured interval must be positive; None disables uploads.
  utest_val(hour, config_interval_s(hour), 'float interval')
  utest_val(None, config_interval_s(None), 'None interval')
  utest_exc(ValueError, config_interval_s, 0.0)
  utest_exc(ValueError, config_interval_s, -hour)

  # A configured interval string is parsed to seconds, just like the `-upload-interval` flag value.
  utest_val(1800.0, config_interval_s('30m'), 'timespan string interval')
  utest_val(None, config_interval_s('never'), '"never" interval')
  utest_exc(ValueError, config_interval_s, 'bogus')
  utest_exc(ValueError, config_interval_s, '0s')

  # Every database must be covered, by its own entry or by the default; an uncovered one is an error, not an implied default.
  utest_exc(ValueError, BackupConfig, db_config=db_config, backups_dir=backups_dir, files={})
  utest_exc(ValueError, BackupConfig, db_config=replace(db_config, names=('main','aux')), backups_dir=backups_dir,
    files=dict(main=BackupFileConfig()))

  # The passed interval is preserved as passed; only the private normalized field holds seconds.
  utest_val('30m', BackupFileConfig(upload_interval='30m').upload_interval, 'upload_interval preserved')

  # The normalized field is derived, so passing it is an error rather than a value that is silently discarded.
  utest_exc(TypeError, BackupFileConfig, upload_interval='30m', _upload_interval_s=1800.0)

  vacuum_path = create_local_backup(backup_config, 'main', method='vacuum')
  utest_val(f'{backups_dir}/main.db', vacuum_path, 'vacuum artifact path')
  utest_val(['original'], read_rows(vacuum_path), 'vacuum artifact rows')


  # Upload intervals: the first upload writes the uploadts sidecar file, and the next timestamp in the same slot skips.
  utest_val(True, maybe_upload(store, vacuum_path, 'main.db', interval=hour), 'initial upload')
  utest_val(True, is_file(vacuum_path + uploadts_suffix, follow=True), 'uploadts written')
  utest_val(False, maybe_upload(store, vacuum_path, 'main.db', interval=hour), 'gated upload skipped')
  utest_val(False, maybe_upload(store, vacuum_path, 'main.db', interval=None), 'interval None never uploads')
  utest_exc(ValueError, maybe_upload, store, vacuum_path, 'main.db', interval=0.0)
  utest_val(1, len(store.versions['main.db']), 'store version count')

  # `force` uploads regardless of the interval and the sidecar file.
  utest_val(True, maybe_upload(store, vacuum_path, 'main.db', interval=hour, force=True), 'force uploads within the slot')
  utest_val(True, maybe_upload(store, vacuum_path, 'main.db', interval=None, force=True), 'force uploads despite None')
  utest_val(3, len(store.versions['main.db']), 'store version count after the forced uploads')


  # Upload intervals resolve per database; the `_` entry is the default and None means never.
  # The per-database keys must name databases in the group, so these use a config with more than one name.
  multi_config = replace(backup_config, db_config=replace(db_config, names=('main','aux','logs')))
  intervals_config = replace(multi_config, files=dict(_=BackupFileConfig(hour), aux=BackupFileConfig(day),
    logs=BackupFileConfig(None)))
  utest(hour, upload_interval_for, intervals_config, 'main')
  utest(day, upload_interval_for, intervals_config, 'aux')
  utest(None, upload_interval_for, intervals_config, 'logs')

  # Naming every database is the alternative to a default entry.
  named_config = replace(multi_config, files=dict(main=BackupFileConfig(upload_interval=hour),
    aux=BackupFileConfig(upload_interval=day), logs=BackupFileConfig()))
  utest(hour, upload_interval_for, named_config, 'main')
  utest(None, upload_interval_for, named_config, 'logs')

  # Per-database intervals are parsed and validated like the default.
  strs_config = replace(multi_config, files=dict(_=BackupFileConfig('1h'), aux=BackupFileConfig('1d'),
    logs=BackupFileConfig('never')))
  utest(hour, upload_interval_for, strs_config, 'main')
  utest(day, upload_interval_for, strs_config, 'aux')
  utest(None, upload_interval_for, strs_config, 'logs')
  utest_exc(ValueError, BackupFileConfig, 0.0)
  utest_exc(ValueError, BackupFileConfig, -hour)
  utest_exc(ValueError, BackupFileConfig, 'bogus')
  utest_exc(ValueError, BackupFileConfig, '0s')

  # A key that does not name a database in the group is an error, not a silent fallback to the default entry.
  utest_exc(ValueError, replace, backup_config, files={'aux': BackupFileConfig(hour)})
  utest_exc(ValueError, replace, multi_config, files={'aux': BackupFileConfig(day), 'bogus': BackupFileConfig(hour)})

  # `_` is reserved as the default key, so it cannot also name a database.
  utest_exc(ValueError, replace, db_config, names=('main', '_'))


  # Triggers: a marker requests an upload regardless of the interval, and is cleared once the upload succeeds.
  trigger_config = replace(backup_config, files=dict(_=BackupFileConfig())) # Uploads are otherwise disabled entirely.
  utest(None, stat_trigger_file, trigger_config, 'main')

  trigger_file = write_trigger_file(trigger_config, 'main')
  utest_val(f'{backups_dir}/main.backuptrigger', trigger_file, 'trigger path')
  utest_val(True, is_file(trigger_file, follow=True), 'trigger written')

  version_count = len(store.versions['main.db'])
  backup_and_upload(trigger_config, ['main'], method='vacuum')
  utest_val(version_count + 1, len(store.versions['main.db']), 'trigger uploads despite uploads being disabled')
  utest_val(False, path_exists(trigger_file, follow=False), 'trigger cleared after a successful upload')

  # Without a trigger, the same config uploads nothing.
  backup_and_upload(trigger_config, ['main'], method='vacuum')
  utest_val(version_count + 1, len(store.versions['main.db']), 'no trigger, no upload')

  # A trigger rewritten after it was claimed is a second request; it must survive the run that was already in flight.
  write_trigger_file(trigger_config, 'main')
  claimed = stat_trigger_file(trigger_config, 'main')
  assert claimed is not None
  sleep(0.01) # So that the rewrite differs in mtime, even if it happens to reuse the freed inode.
  write_trigger_file(trigger_config, 'main')
  clear_trigger_file(trigger_config, 'main', claimed)
  utest_val(True, is_file(trigger_file, follow=True), 'a trigger rewritten during the run is not cleared')

  # The next run consumes it.
  backup_and_upload(trigger_config, ['main'], method='vacuum')
  utest_val(version_count + 2, len(store.versions['main.db']), 'the surviving trigger uploads on the next run')
  utest_val(False, path_exists(trigger_file, follow=False), 'the surviving trigger is then cleared')

  # A failed upload leaves the trigger in place for the next run.
  write_trigger_file(trigger_config, 'main')
  failing_store = FakeStore()
  failing_store.upload = lambda path, obj_key: False # type: ignore[method-assign]
  backup_and_upload(replace(trigger_config, make_save_store=lambda: failing_store), ['main'], method='vacuum')
  utest_val(True, is_file(trigger_file, follow=True), 'a failed upload leaves the trigger in place')
  remove_file_if_exists(trigger_file)


  # Restore: replaces the canonical file with the latest uploaded version and applies the mutation hook.
  with Database.rw(db_config) as db:
    c = db.conn.cursor()
    c.run("INSERT INTO T VALUES ('post-backup')") # A local change that the restore must discard.

  with db_config.exclusive_lock():
    utest_val(True, restore_db(backup_config, store, 'main'), 'restore succeeds')

  utest_val(['mutated', 'original'], read_rows(db_config.path('main')), 'restored rows')
  utest_val(['main'], mutated_names, 'mutation hook called')
  utest_val(1, store.download_count, 'download count')
  utest_val(True, db_config.path('main') in fixed_up_paths, 'canonical path fixed up')

  downloaded_paths = [p for p in fixed_up_paths if p.endswith(downloaded_suffix)]
  utest_val(1, len(downloaded_paths), 'one .downloaded artifact fixed up')
  utest_val(True, path_exists(downloaded_paths[0], follow=False), '.downloaded cache file exists')


  # A second restore of the same version reuses the verified .downloaded cache without downloading.
  with db_config.exclusive_lock():
    utest_val(True, restore_db(backup_config, store, 'main'), 'cached restore succeeds')
  utest_val(1, store.download_count, 'cached restore does not download')


  # A corrupted .downloaded cache file is refused.
  with open(downloaded_paths[0], 'ab') as f:
    f.write(b'garbage')
  with db_config.exclusive_lock():
    utest_val(False, restore_db(backup_config, store, 'main'), 'corrupt cache refused')


  # A version without a SHA1 cannot be verified.
  sha1less_store = FakeStore()
  sha1less_store.versions['main.db'] = [StoredVersion(key='k0', obj_key='main.db', size=0, sha1=None, uploaded_at=now_utc())]
  with db_config.exclusive_lock():
    utest_val(False, restore_db(backup_config, sha1less_store, 'main'), 'sha1-less version refused')


  # An empty store has nothing to restore.
  with db_config.exclusive_lock():
    utest_val(False, restore_db(backup_config, FakeStore(), 'main'), 'empty store refused')


  # Sync backup, if sqlite3_rsync is available.
  if which('sqlite3_rsync'):
    sync_path = create_local_backup(backup_config, 'main', method='sync')
    utest_val(f'{backups_dir}/main.sync.db', sync_path, 'sync artifact path')
    utest_val_ne([], read_rows(sync_path), 'sync artifact has rows')
