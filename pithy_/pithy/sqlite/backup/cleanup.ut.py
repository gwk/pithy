# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pithy.sqlite.backup import BackupConfig, BackupFileConfig, cleanup_downloads
from pithy.sqlite.database import DbConfig
from utest import utest_run, utest_val


@utest_run
def test_cleanup_downloads() -> None:
  with TemporaryDirectory(prefix='backup_cleanup_[test]') as data_dir:
    config = BackupConfig(db_config=DbConfig(names=('main', 'aux', 'empty'), data_dir=data_dir), backups_dir=data_dir,
      files=dict(_=BackupFileConfig(sync_interval=0, upload_interval=None)))
    root = Path(data_dir)
    retained = {'main.db', 'main.db-wal', 'main.db-shm', 'main.db.restoring', 'main.db.prev', 'main.sync.db',
      'main.db.prod_invalid.downloaded', 'main.db.prod_2099-13-01_00_00.downloaded',
      'main.db.prod_2099-01-01_00_00.downloaded.tmp'}
    removed:set[str] = set()
    for name in ('main', 'aux'):
      for store in ('prod', 'prod_extra', 'stage'):
        # Create the older backup last, so modification time must not determine retention.
        for year in (2099, 2098, 2097):
          download = f'{name}.db.{store}_{year}-01-01_00_00.downloaded'
          for suffix in ('', '-wal', '-shm'):
            filename = download + suffix
            (root / filename).write_text(filename)
            (removed if name == 'main' and year < 2099 else retained).add(filename)
    for filename in retained:
      if not (root / filename).exists():
        (root / filename).write_text(filename)
    # Matching directories must be left alone, including a directory with a newer timestamp.
    directory = 'main.db.prod_2100-01-01_00_00.downloaded'
    (root / directory).mkdir()
    retained.add(directory)

    with patch('pithy.sqlite.backup.logI'):
      cleanup_downloads(config, ['main', 'empty'])
      cleanup_downloads(config, ['main', 'empty'])
    actual = {path.name for path in root.iterdir()}
    utest_val(set(), removed & actual, 'older downloads and their sidecars are removed')
    utest_val(set(), retained - actual, 'latest downloads, other databases and unrelated files are retained')
