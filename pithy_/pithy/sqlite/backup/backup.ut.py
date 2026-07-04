# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from hashlib import sha1
from math import inf
from shutil import which
from tempfile import mkdtemp

from pithy.fs import is_file, path_exists
from pithy.logs import adjust_log_level
from pithy.sqlite import Conn
from pithy.sqlite.backup import (BackupConfig, cloudts_suffix, create_local_backup, downloaded_suffix, maybe_upload,
  parse_db_names, parse_upload_interval, restore_db, StoredVersion)
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
utest(0.0, parse_upload_interval, 'always')
utest(inf, parse_upload_interval, 'never')
utest(1800.0, parse_upload_interval, '30m')
utest_exc(ValueError, parse_upload_interval, 'bogus')


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

  backup_config = BackupConfig(db_config=db_config, backups_dir=backups_dir, make_save_store=lambda: store,
    make_restore_store=lambda source: store, mutate_restored=mutate_restored, fix_data_file_perms=fixed_up_paths.append)

  vacuum_path = create_local_backup(backup_config, 'main', method='vacuum')
  utest_val(f'{backups_dir}/main.db', vacuum_path, 'vacuum artifact path')
  utest_val(['original'], read_rows(vacuum_path), 'vacuum artifact rows')


  # Upload interval gating: first upload writes the cloudts sidecar; a fresh timestamp gates the next; zero always uploads.
  utest_val(True, maybe_upload(store, vacuum_path, 'main.db', interval=3600), 'initial upload')
  utest_val(True, is_file(vacuum_path + cloudts_suffix, follow=True), 'cloudts written')
  utest_val(False, maybe_upload(store, vacuum_path, 'main.db', interval=3600), 'gated upload skipped')
  utest_val(True, maybe_upload(store, vacuum_path, 'main.db', interval=0), 'interval zero always uploads')
  utest_val(2, len(store.versions['main.db']), 'store version count')


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
