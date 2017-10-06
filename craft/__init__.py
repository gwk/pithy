# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
import os.path
import plistlib
import re
import yaml
from argparse import ArgumentParser
from typing import *
from pithy.ansi import *
from pithy.dict_utils import dict_set_defaults
from pithy.io import *
from pithy.fs import *
from pithy.json_utils import load_json, parse_json, write_json
from pithy.string_utils import find_and_clip_suffix
from pithy.task import *


CRAFT_PROJECT_DIR = 'CRAFT_PROJECT_DIR'
CRAFT_CONFIG_PATH = 'CRAFT_CONFIG_PATH'
XCODE_DEVELOPER_DIR = 'XCODE_DEVELOPER_DIR'


def load_craft_config():

  try: project_dir = os.environ[CRAFT_PROJECT_DIR]
  except KeyError:
    project_dir = rel_path(find_project_dir(project_signifiers=[r'.+\.craft', *default_project_signifiers]))
    os.environ[CRAFT_PROJECT_DIR] = project_dir

  try: config_path = os.environ[CRAFT_CONFIG_PATH]
  except KeyError:
    names = list_dir(project_dir, exts=['.craft'])
    if not names: exit(f'craft error: no craft file in project dir: {project_dir!r}')
    if len(names) > 1: exit(f'craft error: multiple craft files in project dir: {project_dir!r}; {", ".join(names)}')
    config_path = normalize_path(path_join(project_dir, names[0]))
    os.environ[CRAFT_CONFIG_PATH] = config_path

  # TODO: Xcode is macOS only.
  try: xcode_dev_dir = os.environ[XCODE_DEVELOPER_DIR]
  except KeyError:
    c, dev_dir_line = runCO('xcode-select --print-path')
    if c: exit("craft error: 'xcode-select --print-path' failed; could not determine XCODE_DEVELOPER_DIR.")
    xcode_dev_dir = dev_dir_line.rstrip('\n')
    os.environ[XCODE_DEVELOPER_DIR] = xcode_dev_dir

  config = parse_craft(config_path)
  config['config-path'] = config_path
  config['project-dir'] = project_dir
  config['xcode-dev-dir'] = xcode_dev_dir

  c = CraftConfig(**{k.replace('-', '_'): v for (k, v) in config.items()})

  if not is_sub_path(c.build_dir): exit(f'craft error: build-dir must be a subpath: {c.build_dir!r}')

  if c.target_macOS and not re.fullmatch(r'\d+\.\d+', c.target_macOS):
    exit(f"craft error: target-macOS should be 'MAJOR.MINOR' number; received {c.target_macOS!r}")

  return c


def parse_craft(path):
  try: f = open(path)
  except FileNotFoundError: exit(f'craft error: craft file does not exist: {path!r}')
  with f: d = yaml.load(f)
  for k, v in d.items():
    if k in craft_nonconfigurable_keys: exit(f'craft error: key is not configurable: {k!r}')
    if k not in craft_configurable_keys: exit(f'craft error: invalid craft config key: {k!r}')
  missing_keys = craft_required_keys.difference(d)
  if missing_keys: exit('\n  '.join([f'craft error: missing required keys in {path!r}:', *sorted(missing_keys)]))
  dict_set_defaults(d, craft_config_defaults)
  return d


def update_swift_package_json(config) -> Any:
  src = 'Package.swift'
  dst = f'{config.build_dir}/swift-package.json'
  if product_needs_update(dst, source=src):
    dev_dir = config.xcode_dev_dir
    lib_pm_4_dir = dev_dir + '/Toolchains/XcodeDefault.xctoolchain/usr/lib/swift/pm/4'
    cmd = [
      'swiftc',
      '--driver-mode=swift',
      '-swift-version', '4',
      '-target', 'x86_64-apple-macosx10.10',
      '-sdk', dev_dir + '/Platforms/MacOSX.platform/Developer/SDKs/MacOSX10.13.sdk',
      '-I', lib_pm_4_dir,
      '-L', lib_pm_4_dir,
      '-lPackageDescription',
      'Package.swift',
      '-fileno', '1',
    ]
    try: o = runO(cmd)
    except TaskUnexpectedExit as e: exit(1)
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
  xcode_dev_dir: str
  product_name: Optional[str] = None
  product_identifier: Optional[str] = None
  sources: Optional[str] = None

  @property
  def target_triple_macOS(self) -> str: return f'x86_64-apple-macosx{self.target_macOS}'


craft_required_keys = frozenset({
  'copyright'
})

craft_config_defaults = {
  'copyright': 'Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.',
  'build-dir': '_build',
  'target-macOS': '10.13',
}

craft_configurable_keys = frozenset({
  *craft_required_keys,
  *craft_config_defaults,
  'product-name',
  'product-identifier',
  'sources',
})

craft_nonconfigurable_keys = frozenset({
  'config-path',
  'project-dir',
  'xcode-dev-dir',
})


class Private(NamedTuple):
  sym: str


def handle_yaml_private(loader, node) -> str:
  return Private(sym=resolve_yaml_node(node.value))

def resolve_yaml_node(node: Any) -> Any:
  if isinstance(node, yaml.Node): return resolve_yaml_node(node.value)
  if isinstance(node, list): return [resolve_yaml_node(n) for n in node]
  if isinstance(node, dict): return {resolve_yaml_node(k): resolve_yaml_node(v) for k, v in node.value.items()}
  return node


# NOTE: modifies the global default yaml Loader object.
yaml.add_constructor('!private', handle_yaml_private)

