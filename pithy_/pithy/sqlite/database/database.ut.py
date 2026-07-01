# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from tempfile import mkdtemp

from pithy.sqlite.database import DbConfig, manifest_filename
from utest import utest, utest_exc, utest_val


# `manifest_dict` omits `data_dir` and includes the layout and policy fields.
config = DbConfig(names=('main', 'aux'), data_dir='/some/dir', user_version=3, cache_mb=64, synchronous_full=True,
  lock_allow_group=False)
utest({
  'names': ['main', 'aux'],
  'user_version': 3,
  'cache_mb': 64,
  'synchronous_full': True,
  'lock_allow_group': False,
}, config.manifest_dict)


# Round-trip through the manifest file reconstructs an equal config, with `data_dir` taken from the load directory.
data_dir = mkdtemp(prefix='dbconfig_ut')
config_here = DbConfig(names=('main', 'aux'), data_dir=data_dir, user_version=3, cache_mb=64, synchronous_full=True,
  lock_allow_group=False)
config_here.write_manifest()
utest(config_here, DbConfig.load_manifest, data_dir)

# `manifest_path` is the canonical filename within the data dir.
utest_val(f'{data_dir}/{manifest_filename}', config_here.manifest_path, 'manifest_path')


# Loading from a directory without a manifest raises.
empty_dir = mkdtemp(prefix='dbconfig_ut_empty')
utest_exc(FileNotFoundError, DbConfig.load_manifest, empty_dir)
