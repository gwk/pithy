# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from hashlib import sha1
from os import environ
from shutil import which
from tempfile import mkdtemp
from time import tzset

from pithy.date import DateTime, TimeDelta
from pithy.fs import is_file, path_exists
from pithy.logs import adjust_log_level
from pithy.sqlite import Conn
from pithy.sqlite.backup import (BackupConfig, cloudts_suffix, create_local_backup, downloaded_suffix, interval_slot,
  maybe_upload, parse_db_names, parse_upload_interval, restore_db, StoredVersion)
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

# An interval longer than a day is equally periodic; its phase is fixed by the epoch, which fell on a Thursday.
# Pacific weekly slots therefore begin at 00:00 PST on Thursdays.
utest_val(slot('2026-01-07T23:59:59-08:00', interval=7*day) + 1, slot('2026-01-08T00:00:00-08:00', interval=7*day),
  'weekly slots begin at 00:00 PST on Thursday')
weekly = slots_from('2026-01-08T00:00:00-08:00', count=4, step=TimeDelta(days=7), interval=7*day)
utest_val(list(range(weekly[0], weekly[0]+4)), weekly, 'weekly slots advance by one per 7 elapsed days')

# The standard-time phase holds for multi-day intervals too, so under daylight saving the boundary is 01:00 local.
utest_val(slot('2026-03-12T00:59:59-07:00', interval=7*day) + 1, slot('2026-03-12T01:00:00-07:00', interval=7*day),
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

  backup_config = BackupConfig(db_config=db_config, backups_dir=backups_dir, upload_interval=hour,
    make_save_store=lambda: store, make_restore_store=lambda source: store, mutate_restored=mutate_restored,
    fix_data_file_perms=fixed_up_paths.append)

  def config_interval_s(upload_interval:float|str|None) -> float|None:
    'Construct a config with the given upload interval and return the normalized seconds.'
    return BackupConfig(db_config=db_config, backups_dir=backups_dir, upload_interval=upload_interval)._upload_interval_s

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

  # The passed interval is preserved as passed; only the private normalized field holds seconds.
  utest_val('30m', BackupConfig(db_config=db_config, backups_dir=backups_dir, upload_interval='30m').upload_interval,
    'upload_interval preserved')

  vacuum_path = create_local_backup(backup_config, 'main', method='vacuum')
  utest_val(f'{backups_dir}/main.db', vacuum_path, 'vacuum artifact path')
  utest_val(['original'], read_rows(vacuum_path), 'vacuum artifact rows')


  # Upload intervals: the first upload writes the cloudts sidecar file, and the next timestamp in the same slot skips.
  utest_val(True, maybe_upload(store, vacuum_path, 'main.db', interval=hour), 'initial upload')
  utest_val(True, is_file(vacuum_path + cloudts_suffix, follow=True), 'cloudts written')
  utest_val(False, maybe_upload(store, vacuum_path, 'main.db', interval=hour), 'gated upload skipped')
  utest_val(False, maybe_upload(store, vacuum_path, 'main.db', interval=None), 'interval None never uploads')
  utest_exc(ValueError, maybe_upload, store, vacuum_path, 'main.db', interval=0.0)
  utest_val(1, len(store.versions['main.db']), 'store version count')


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
