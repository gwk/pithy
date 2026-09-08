# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import ANY, patch

from pithy.sqlite.backup import BackupConfig, BackupFileConfig, main_entry
from pithy.sqlite.database import DbConfig
from utest import utest_exc, utest_run


@utest_run
def test_cli() -> None:
  config = BackupConfig(db_config=DbConfig(names=('main', 'aux'), data_dir='unused'), backups_dir='unused',
    files=dict(_=BackupFileConfig(sync_interval=0, upload_interval=None)))

  for source in (config, lambda: config, 'example:config', None):
    app_args = ['-app', 'example:config'] if source is None else []
    with patch('pithy.sqlite.backup.resolve_backup_config', return_value=config) as resolve:
      for method_args, method in (([], 'sync'), (['-method', 'vacuum'], 'vacuum'), (['--method=sync'], 'sync')):
        with patch('pithy.cmdparse.sys_argv', ['backup', 'save', *app_args, *method_args, 'all']), \
         patch('pithy.sqlite.backup.backup_and_upload') as save:
          main_entry(source)
        resolve.assert_called_with('example:config' if source is None else source)
        save.assert_called_once_with(config, ('main', 'aux'), method=method, should_stop=ANY)

      with patch('pithy.cmdparse.sys_argv', ['backup', 'trigger', *app_args, 'aux']), \
       patch('pithy.sqlite.backup.write_trigger_file', return_value='unused') as trigger, \
       patch('pithy.sqlite.backup.logI'):
        main_entry(source)
      trigger.assert_called_once_with(config, 'aux')

      for options, store, local in (([], None, False), (['-local', '-store', 'prod'], 'prod', True)):
        with patch('pithy.cmdparse.sys_argv', ['backup', 'restore', *app_args, *options, 'main', 'aux']), \
         patch('pithy.sqlite.backup.restore_all') as restore:
          main_entry(source)
        restore.assert_called_once_with(config, ('main', 'aux'), store_name=store, local=local)

      # Invalid input and help must not resolve application configuration or perform backup operations.
      resolve.reset_mock()
      for args in ([], ['save', *app_args], ['trigger', *app_args], ['restore', *app_args],
       ['save', *app_args, '-method', 'invalid', 'all'], ['save', '-app']):
        with patch('pithy.cmdparse.sys_argv', ['backup', *args]), patch('pithy.cmdparse.stderr', new_callable=StringIO):
          utest_exc(SystemExit(2), main_entry, source)
      if source is None:
        for args in (['save', 'all'], ['trigger', 'all'], ['restore', 'all']):
          with patch('pithy.cmdparse.sys_argv', ['backup', *args]), patch('pithy.cmdparse.stderr', new_callable=StringIO):
            utest_exc(SystemExit('error: -app is required when no backup config source is supplied.'), main_entry, source)
      for args in (['-h'], ['save', '-h'], ['trigger', '-h'], ['restore', '-h']):
        with patch('pithy.cmdparse.sys_argv', ['backup', *args]), redirect_stdout(StringIO()):
          utest_exc(SystemExit(0), main_entry, source)
      resolve.assert_not_called()


  # Explicit application options override a wrapper's default config source.
  with patch('pithy.cmdparse.sys_argv', ['backup', 'restore', '--app=other:config', 'all']), \
   patch('pithy.sqlite.backup.resolve_backup_config', return_value=config) as resolve, \
   patch('pithy.sqlite.backup.restore_all') as restore:
    main_entry(config)
  resolve.assert_called_once_with('other:config')
  restore.assert_called_once_with(config, ('main', 'aux'), store_name=None, local=False)
