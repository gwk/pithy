# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
import os.path
import re
from tomllib import load as load_toml, TOMLDecodeError
from typing import Any, NamedTuple

from pithy.fs import find_project_dir, list_dir, path_for_cmd, real_path
from pithy.path import is_sub_path, norm_path, path_ext, path_join, path_name_stem, path_split, rel_path
from pithy.task import runO


CRAFT_PROJECT_DIR = 'CRAFT_PROJECT_DIR'
CRAFT_CONFIG_PATH = 'CRAFT_CONFIG_PATH'
CRAFT_SWIFT_PATH = 'CRAFT_SWIFT_PATH'
XCODE_DEVELOPER_DIR = 'XCODE_DEVELOPER_DIR'
XCODE_TOOLCHAIN_DIR = 'XCODE_TOOLCHAIN_DIR'


class CraftConfig(NamedTuple):
  build_dir: str = '.build'
  config_path: str = '' # Derived.
  copyright: str = '' # Required.
  product_identifier: str|None = None
  product_name: str|None = None
  project_dir: str = '' # Derived.
  resources: dict[str, str] = {}
  sources: str = 'src'
  swift_path: str = '' # Derived.
  swift_version: str = None # type: ignore[assignment] # TODO
  target_macOS: str = None # type: ignore[assignment] # TODO
  ts_modules: dict[str, str] = {}
  xcode_dev_dir: str = '' # Derived.
  xcode_toolchain_dir: str = '' # Derived.

  @property
  def target_triple_macOS(self) -> str: return f'arm64-apple-macosx{self.target_macOS}'


def load_craft_config() -> CraftConfig:

  try: project_dir = os.environ[CRAFT_PROJECT_DIR]
  except KeyError:
    p = find_project_dir()
    if p is None: exit('craft error: could not identify project directory.')
    project_dir = rel_path(p)
    os.environ[CRAFT_PROJECT_DIR] = project_dir

  try: config_path = os.environ[CRAFT_CONFIG_PATH]
  except KeyError:
    names = [n for n in list_dir(project_dir) if path_name_stem(n) == 'craft']
    if not names: exit(f'craft error: no craft file in project dir: {project_dir!r}')
    if len(names) > 1: exit(f'craft error: multiple craft files in project dir: {project_dir!r}; {", ".join(names)}')
    config_path = norm_path(path_join(project_dir, names[0]))
    os.environ[CRAFT_CONFIG_PATH] = config_path

  try: swift_path = os.environ[CRAFT_SWIFT_PATH]
  except KeyError:
    p = path_for_cmd('swift')
    if p is None: exit('craft error: no path to `swift` executable')
    swift_path = p
  os.environ[CRAFT_SWIFT_PATH] = swift_path

  # TODO: Xcode is macOS only.
  try: xcode_dev_dir = os.environ[XCODE_DEVELOPER_DIR]
  except KeyError:
    xcode_dev_dir = find_dev_dir()
    os.environ[XCODE_DEVELOPER_DIR] = xcode_dev_dir

  try: xcode_toolchain_dir = os.environ[XCODE_TOOLCHAIN_DIR]
  except KeyError:
    xcode_toolchain_dir = find_toolchain_dir(swift_path, xcode_dev_dir)
    os.environ[XCODE_TOOLCHAIN_DIR] = xcode_toolchain_dir

  config = parse_craft(config_path)
  config['config_path'] = config_path
  config['project_dir'] = project_dir
  config['swift_path'] = swift_path
  config['xcode_dev_dir'] = xcode_dev_dir
  config['xcode_toolchain_dir'] = xcode_toolchain_dir

  c = CraftConfig(**config) # TODO: validate types.

  if not is_sub_path(c.build_dir): exit(f'craft error: build_dir must be a subpath: {c.build_dir!r}')

  if c.swift_version and not re.fullmatch(r'\d+(\.\d+)?', c.swift_version):
    exit(f"craft error: swift_version should be 'MAJOR' or MAJOR.MINOR' number; received {c.swift_version!r}")

  if c.target_macOS and not re.fullmatch(r'\d+\.\d+', c.target_macOS):
    exit(f"craft error: target_macOS should be 'MAJOR.MINOR' number; received {c.target_macOS!r}")

  return c


def parse_craft(path:str) -> dict[str,Any]:
  try:
    with open(path, 'rb') as f:
      if path_ext(path) == '.toml':
        d = load_toml(f)
      else:
        exit('craft error: craft file must be a `.toml` file.') # TODO: relax this restriction.
  except FileNotFoundError:
    exit(f'craft error: craft file does not exist: {path!r}')
  except TOMLDecodeError as e:
    fail_on_toml_error(path, e)

  for k, v in d.items():
    if k in craft_nonconfigurable_keys: exit(f'craft error: key is not configurable: {k!r}')
    if k not in craft_configurable_keys: exit(f'craft error: invalid craft config key: {k!r}')

  missing_keys = craft_required_keys.difference(d)
  if missing_keys: exit('\n  '.join([f'craft error: missing required keys in {path!r}:', *sorted(missing_keys)]))

  return d


def fail_on_toml_error(path:str, e:TOMLDecodeError) -> None:
  m = toml_error_re.fullmatch(str(e))
  if m:
    msg, line, col = m.groups()
    exit(f'{path}:{line}:{col}: toml error: {msg}.')
  else:
    exit(f'{path}: toml error: {e}.')


toml_error_re = re.compile(r'(.+) \(at line (\d+), column (\d+)\)')
craft_required_keys = frozenset({
  'copyright'
})


# TODO: derive this from CraftConfig class def.
craft_configurable_keys = frozenset({
  *craft_required_keys,
  'copyright',
  'product_name',
  'product_identifier',
  'sources',
  'swift_version',
  'resources',
  'target_macOS',
  'ts_modules',
})

craft_nonconfigurable_keys = frozenset({
  'config_path',
  'project_dir',
  'xcode_dev_dir',
})


def find_dev_dir() -> str:
  dev_dir_line = runO('xcode-select --print-path',
    exits="craft error: 'xcode-select --print-path' failed; could not determine XCODE_DEVELOPER_DIR.")
  return dev_dir_line.rstrip('\n')


def find_toolchain_dir(swift_path:str, dev_dir:str) -> str:
  if swift_path is None: exit('no `swift` executable found in PATH.')
  parts = path_split(real_path(swift_path))
  for i, part in enumerate(parts):
    if path_ext(part) == '.xctoolchain':
      return path_join(*parts[:i+1])
  # default to dev dir.
  return f'{dev_dir}/Toolchains/XcodeDefault.xctoolchain'
