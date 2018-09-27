# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from pithy.ansi import *
from pithy.dict import dict_set_defaults
from pithy.fs import *
from pithy.io import *
from pithy.json import load_json, parse_json, write_json
from pithy.string import find_and_clip_suffix
from pithy.task import runO
from typing import Any, AnyStr, Dict, cast
import os
import os.path
import plistlib
import re
import yaml


CRAFT_PROJECT_DIR = 'CRAFT_PROJECT_DIR'
CRAFT_CONFIG_PATH = 'CRAFT_CONFIG_PATH'
CRAFT_SWIFT_PATH = 'CRAFT_SWIFT_PATH'
XCODE_DEVELOPER_DIR = 'XCODE_DEVELOPER_DIR'
XCODE_TOOLCHAIN_DIR = 'XCODE_TOOLCHAIN_DIR'


def load_craft_config():

  try: project_dir = os.environ[CRAFT_PROJECT_DIR]
  except KeyError:
    p = find_project_dir()
    if p is None: exit(f'craft error: could not identify project directory.')
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
    if p is None: exit(f'craft error: no path to `swift` executable')
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
  config['config-path'] = config_path
  config['project-dir'] = project_dir
  config['swift-path'] = swift_path
  config['xcode-dev-dir'] = xcode_dev_dir
  config['xcode-toolchain-dir'] = xcode_toolchain_dir

  c = CraftConfig(**{k.replace('-', '_'): v for (k, v) in config.items()}) # TODO: validate types.

  if not is_sub_path(c.build_dir): exit(f'craft error: build-dir must be a subpath: {c.build_dir!r}')

  if c.target_macOS and not re.fullmatch(r'\d+\.\d+', c.target_macOS):
    exit(f"craft error: target-macOS should be 'MAJOR.MINOR' number; received {c.target_macOS!r}")

  return c


def parse_craft(path:str) -> Dict[str,Any]:
  try: f = open(path)
  except FileNotFoundError: exit(f'craft error: craft file does not exist: {path!r}')
  if path_ext(path) != '.yaml': exit(f'craft error: caft file must be a `.yaml` file.') # TODO: relax this restriction.
  with f: d = yaml.load(f)
  for k, v in d.items():
    if k in craft_nonconfigurable_keys: exit(f'craft error: key is not configurable: {k!r}')
    if k not in craft_configurable_keys: exit(f'craft error: invalid craft config key: {k!r}')
  missing_keys = craft_required_keys.difference(d)
  if missing_keys: exit('\n  '.join([f'craft error: missing required keys in {path!r}:', *sorted(missing_keys)]))
  dict_set_defaults(d, craft_config_defaults)
  return cast(Dict[str,Any], d)


def update_swift_package_json(config) -> Any:
  make_dirs(config.build_dir)
  src = 'Package.swift'
  dst = f'{config.build_dir}/swift-package.json'
  if product_needs_update(dst, source=src):
    dev_dir = config.xcode_dev_dir
    lib_pm_4_dir = f'{config.xcode_toolchain_dir}/usr/lib/swift/pm/4'
    cmd = [
      'swiftc',
      '--driver-mode=swift',
      '-swift-version', '4',
      '-target', 'x86_64-apple-macosx10.10',
      '-sdk', dev_dir + '/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.14.sdk',
      '-I', lib_pm_4_dir,
      '-L', lib_pm_4_dir,
      '-lPackageDescription',
      'Package.swift',
      '-fileno', '1',
    ]
    o = runO(cmd, exits=True)
    data = parse_json(o)
    with open(dst, 'w') as f:
      write_json(f, data)
    return data
  else:
    return load_json(open(dst))


class CraftConfig(NamedTuple):
  build_dir: str
  config_path: str
  copyright: str
  project_dir: str
  target_macOS: str
  swift_path: str
  xcode_dev_dir: str
  xcode_toolchain_dir: str
  product_name: Optional[str] = None
  product_identifier: Optional[str] = None
  sources: str = 'src'
  resources: Dict[str, str] = {}
  ts_modules: Dict[str, str] = {}

  @property
  def target_triple_macOS(self) -> str: return f'x86_64-apple-macosx{self.target_macOS}'


craft_required_keys = frozenset({
  'copyright'
})

craft_config_defaults = {
  'copyright': 'Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.',
  'build-dir': '_build',
  'target-macOS': '10.14',
}

# TODO: derive this from CraftConfig class def.
craft_configurable_keys = frozenset({
  *craft_required_keys,
  *craft_config_defaults,
  'product-name',
  'product-identifier',
  'sources',
  'resources',
  'ts-modules',
})

craft_nonconfigurable_keys = frozenset({
  'config-path',
  'project-dir',
  'xcode-dev-dir',
})


def find_dev_dir() -> str:
  dev_dir_line = runO('xcode-select --print-path',
    exits="craft error: 'xcode-select --print-path' failed; could not determine XCODE_DEVELOPER_DIR.")
  return dev_dir_line.rstrip('\n')


def find_toolchain_dir(swift_path:str, dev_dir:str) -> str:
  if swift_path is None: exit('no `swift` executable found in PATH.')
  path = real_path(swift_path)
  parts = path_split(swift_path)
  for i, part in enumerate(parts):
    if path_ext(part) == '.xctoolchain':
      return path_join(*parts[:i+1])
  # default to dev dir.
  return f'{dev_dir}/Toolchains/XcodeDefault.xctoolchain'


class Private(NamedTuple):
  sym: str


def handle_yaml_private(loader, node) -> Private:
  return Private(sym=resolve_yaml_node(node.value))

def resolve_yaml_node(node: Any) -> Any:
  if isinstance(node, yaml.Node): return resolve_yaml_node(node.value)
  if isinstance(node, list): return [resolve_yaml_node(n) for n in node]
  if isinstance(node, dict): return {resolve_yaml_node(k): resolve_yaml_node(v) for k, v in node.items()}
  return node


# NOTE: modifies the global default yaml Loader object.
yaml.add_constructor('!private', handle_yaml_private) # type: ignore

