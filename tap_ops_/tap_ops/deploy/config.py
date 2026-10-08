# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''The versioned deployment policy stored alongside each build's unit files.'''

import math
import re
import tomllib
from dataclasses import dataclass

from pithy.filestatus import is_file, is_link
from pithy.io import read_from_path
from pithy.path import Path

from ..systemd.reconciliation import read_source, ReconciliationError, unit_name
from .errors import DeployError


_context_keywords_ = ['configuration', 'readiness', 'systemd', 'toml']


@dataclass(frozen=True)
class UnitConfig:
  enable:bool
  start:bool
  ready_log:str = ''
  message_key:str = '_'


@dataclass(frozen=True)
class DeployConfig:
  units:dict[str,UnitConfig]
  settle:float = 20
  timeout:float = 120

  @property
  def enabled(self) -> list[str]: return sorted(n for n, u in self.units.items() if u.enable)

  @property
  def started(self) -> list[str]: return sorted(n for n, u in self.units.items() if u.start)


def read_config(path:Path, units_dir:Path) -> DeployConfig:
  'Read a policy and require an exact match between its inventory and the supplied unit files.'
  if is_link(path) or not is_file(path, follow=False): raise DeployError(f'Expected a deployment config file: {path}.')
  try:
    config = parse_config(tomllib.loads(read_from_path(path)))
    files = read_source(units_dir)
  except (tomllib.TOMLDecodeError, UnicodeError, ReconciliationError) as exc:
    raise DeployError(f'Invalid deployment config: {path}: {exc}') from exc
  missing = sorted(set(config.units) - files.keys())
  undeclared = sorted(files.keys() - config.units.keys())
  if missing or undeclared:
    raise DeployError(f'Deployment unit inventory mismatch: missing files: {missing}; undeclared files: {undeclared}.')
  # Systemd accepts a request to enable a unit that has no installation config, but leaves the unit static.
  if static := [n for n in config.enabled if not re.search(rb'^\[Install\][ \t]*$', files[n], flags=re.MULTILINE)]:
    raise DeployError(f'Units declare enable = true but have no [Install] section: {static}.')
  return config


def parse_config(data:object) -> DeployConfig:
  config = _table(data, 'deployment', {'version', 'units', 'verify'})
  if type(config.get('version')) is not int or config['version'] != 1:
    raise DeployError('Deployment config version must be 1.')
  raw_units = config.get('units')
  if not isinstance(raw_units, dict) or not raw_units: raise DeployError('Deployment config must declare at least one unit.')
  units:dict[str,UnitConfig] = {}
  for name, value in raw_units.items():
    try: name = unit_name(name)
    except ReconciliationError as exc: raise DeployError(str(exc)) from exc
    unit = _table(value, name, {'enable', 'start', 'ready_log', 'message_key'})
    for field in ('enable', 'start'):
      if type(unit.get(field)) is not bool: raise DeployError(f'{name}: {field} must be an explicit boolean.')
    ready_log = unit.get('ready_log', '')
    message_key = unit.get('message_key', '_')
    if not isinstance(ready_log, str): raise DeployError(f'{name}: ready_log must be a string.')
    if not isinstance(message_key, str) or not message_key: raise DeployError(f'{name}: message_key must be nonempty.')
    if not unit['start'] and ('ready_log' in unit or 'message_key' in unit):
      raise DeployError(f'{name}: readiness settings require start = true.')
    try: re.compile(ready_log)
    except re.error as exc: raise DeployError(f'{name}: invalid ready_log: {exc}') from exc
    units[name] = UnitConfig(enable=unit['enable'], start=unit['start'], ready_log=ready_log, message_key=message_key)
  verify = _table(config.get('verify', {}), 'verify', {'settle', 'timeout'})
  settle = _seconds(verify.get('settle', 20), 'settle')
  timeout = _seconds(verify.get('timeout', 120), 'timeout')
  if timeout <= 0 or timeout < settle: raise DeployError('Verification timeout must be positive and at least settle.')
  return DeployConfig(units=units, settle=settle, timeout=timeout)


def _table(value:object, name:str, keys:set[str]) -> dict:
  if not isinstance(value, dict): raise DeployError(f'{name}: expected a table.')
  if unknown := value.keys() - keys: raise DeployError(f'{name}: unknown fields: {sorted(unknown)}.')
  return value


def _seconds(value:object, name:str) -> float:
  if type(value) not in (int, float) or not isinstance(value, (int, float)):
    raise DeployError(f'Verification {name} must be a number of seconds.')
  if not math.isfinite(value) or value < 0: raise DeployError(f'Verification {name} must be finite and nonnegative.')
  return float(value)
