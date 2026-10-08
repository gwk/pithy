# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pathlib import Path as StdPath
from tempfile import TemporaryDirectory

from pithy.path import Path
from tap_ops.deploy.config import DeployConfig, parse_config, read_config, UnitConfig
from tap_ops.deploy.errors import DeployError
from utest import utest_exc, utest_run, utest_val


valid = {'version': 1, 'units': {'web.service': {'enable': True, 'start': True}}}
utest_val(DeployConfig(units={'web.service': UnitConfig(enable=True, start=True)}), parse_config(valid))

for data in (
  {}, {**valid, 'version': True}, {**valid, 'version': 2}, {**valid, 'extra': 1}, {**valid, 'units': {}},
  {**valid, 'units': {'web.service': {'enable': True}}},
  {**valid, 'units': {'web.service': {'enable': 1, 'start': True}}},
  {**valid, 'units': {'../web.service': {'enable': True, 'start': True}}},
  {**valid, 'units': {'web.service': {'enable': True, 'start': True, 'strat': True}}},
  {**valid, 'units': {'web.service': {'enable': True, 'start': False, 'ready_log': 'ready'}}},
  {**valid, 'units': {'web.service': {'enable': True, 'start': True, 'ready_log': '['}}},
  {**valid, 'units': {'web.service': {'enable': True, 'start': True, 'message_key': ''}}},
  {**valid, 'verify': {'settle': -1}}, {**valid, 'verify': {'timeout': 0}},
  {**valid, 'verify': {'timeout': 1}}, {**valid, 'verify': {'settle': True}},
  {**valid, 'verify': {'timeout': float('inf')}}, {**valid, 'verify': {'settle': float('nan')}},
  {**valid, 'verify': {'typo': 1}},
):
  utest_exc(DeployError, parse_config, data)


@utest_run
def test_inventory() -> None:
  with TemporaryDirectory() as tmp:
    root = StdPath(tmp)
    units = root / 'units'
    units.mkdir()
    path = root / 'deploy.toml'
    path.write_text('version = 1\n[units."web.service"]\nenable = true\nstart = true\n')
    utest_exc(DeployError("Deployment unit inventory mismatch: missing files: ['web.service']; undeclared files: []."),
      read_config, Path(path), Path(units))
    (units / 'web.service').write_text('[Service]\nExecStart=/bin/true\n')
    utest_exc(DeployError("Units declare enable = true but have no [Install] section: ['web.service']."),
      read_config, Path(path), Path(units))
    (units / 'web.service').write_text('[Service]\nExecStart=/bin/true\n\n[Install]\nWantedBy=multi-user.target\n')
    utest_val(['web.service'], read_config(Path(path), Path(units)).started)
    (units / 'extra.timer').write_text('[Timer]\nOnCalendar=daily\n')
    utest_exc(DeployError("Deployment unit inventory mismatch: missing files: []; undeclared files: ['extra.timer']."),
      read_config, Path(path), Path(units))
    path.write_text('version = [')
    utest_exc(DeployError, read_config, Path(path), Path(units))
