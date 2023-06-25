# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-swift-utest` is a small test harness for running unit tests, with no dependency on XCTest.
It is currently a work in progress and is somewhat out of date.
'''

from argparse import ArgumentParser
from typing import Dict, Iterator, NamedTuple

from crafts import CraftConfig, load_craft_config
from pithy.fs import make_dirs, remove_dir_contents, walk_files
from pithy.io import errL, errSL, outL
from pithy.iterable import fan_by_key_fn
from pithy.path import is_sub_path, path_ext, path_join, path_name, path_rel_to_dir, path_stem, rel_path, replace_first_dir
from pithy.swift.demangle import parse_nm_line
from pithy.task import run, runC, runCO
from yaml import safe_load as load_yaml


def main() -> None:
  arg_parser = ArgumentParser(description='Swift unit test tool.')
  arg_parser.add_argument('test_paths', nargs='+')
  args = arg_parser.parse_args()

  for path in args.test_paths:
    if not is_sub_path(path): exit(f'craft-swift-utest error: test path must be a subpath of the project: {path!r}')

  conf = load_craft_config()

  run(['craft-swift'], exits=True)

  dev_dir = conf.xcode_dev_dir
  sdk_dir = f'{dev_dir}/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk' # The versioned SDK just links to the unversioned one. # TODO: dedup with mac_app.
  fw_dir = f'{dev_dir}/Platforms/MacOSX.platform/Developer/Library/Frameworks'
  build_dir = conf.build_dir
  debug_dir = f'{build_dir}/debug'
  debug_yaml_path = f'{build_dir}/debug.yaml'
  module_cache_dir = f'{debug_dir}/ModuleCache'

  try: debug_yaml = load_yaml(open(debug_yaml_path))
  except Exception as e: raise Exception(f'error: failed to load debug.yaml: {debug_yaml_path!r}') from e

  modules:Dict[str,Module] = {}
  source_modules:Dict[str,Module] = {}
  for name, command in debug_yaml['commands'].items():
    if command['tool'] != 'swift-compiler': continue
    module_name = command['module-name']
    if module_name in modules: exit(f'error: module name appears multiple times in swift build output: {module_name}')
    module = Module(
      name=module_name,
      module_build_dir=rel_path(command['temps-path']),
      inputs=fan_by_key_fn((rel_path(p) for p in command['inputs']), key=path_ext))
    modules[module_name] = module
    for swift_path in module.inputs['.swift']:
      if swift_path in source_modules:
        exit(f'error: swift source appears in multiple modules: {swift_path}; modules: {source_modules[swift_path]}, {module.name}.')
      source_modules[swift_path] = module

  ok = True
  for path in args.test_paths:
    path = rel_path(path)
    if path.startswith('src/'):
      # This is a hack to make unit testing in VSCode easier
      # TODO: generalize to the project source directories, rather than hardcoded 'src'.
      test_path = replace_first_dir(path, 'test/')
      errL(f'craft-swift-utest: assuming {path} -> {test_path}')
      path = test_path
    for src_path in walk_files(path, file_exts=['.swift']):
      try: module = source_modules[src_path]
      except KeyError: errL(f'warning: no module source found for utest: {src_path}')
      ok &= run_utest(src_path=src_path, module=module, conf=conf, debug_dir=debug_dir, sdk_dir=sdk_dir, fw_dir=fw_dir, module_cache_dir=module_cache_dir)
  if not ok: exit(1)


class Module(NamedTuple):
  name: str
  module_build_dir: str
  inputs: Dict[str, list[str]]


def run_utest(src_path:str, module:Module, conf:CraftConfig, debug_dir:str, sdk_dir:str, fw_dir:str, module_cache_dir:str) -> bool:
  outL(f'craft-swift-utest: {module.name}: {src_path}')
  build_dir = conf.build_dir
  stem = path_stem(src_path)
  name = path_name(stem)
  test_dir = f'{build_dir}/{stem}'
  o_path = f'{module.module_build_dir}/{name}.swift.o'

  if test_dir.lower().startswith(debug_dir.lower()): exit(f'error: unit test stem collides with debug build directory: {stem}')
  make_dirs(test_dir)
  remove_dir_contents(test_dir)
  main_path = f'{test_dir}/main.swift'
  exe_path = f'{test_dir}/{name}'
  debug_dir_rpath = path_join('@executable_path', path_rel_to_dir(debug_dir, test_dir))

  test_syms = list(scan_test_syms(module.name, o_path))

  with open(main_path, 'w') as f:
    f.write(f'@testable import {module.name}\n\n')
    for sym in test_syms:
      f.write(f'{sym}()\n')

  cmd = [
    'swiftc',
    '-sdk', sdk_dir,
    '-F', fw_dir,
    '-I', debug_dir,
    '-L', debug_dir,
    '-module-cache-path', module_cache_dir,
    '-swift-version', conf.swift_version,
    '-target', conf.target_triple_macOS,
    '-Onone',
    '-g',
    '-enable-testing',
    '-module-name', name,
    '-emit-executable',
    '-Xlinker', '-rpath',
    '-Xlinker', debug_dir_rpath,
    '-l' + module.name,
    '-o', f'{test_dir}/{name}',
    main_path,
  ]
  #errSL('CMD:', sh_join(cmd))
  if runC(cmd) != 0:
    errSL('utest compile failed:', *cmd)
    return False
  if runC(exe_path) != 0:
    errSL('utest failed:', exe_path)
    return False
  return True


def scan_test_syms(module_name:str, o_path:str) -> Iterator[str]:
  c, o = runCO(['nm', o_path,  '-g', '-U', '-m', '-s', '__TEXT', '__text'])
  if c != 0: exit(f'error: failed to scan top-level symbols: {o_path}')
  for line in o.splitlines():
    _, _, descriptors, name_parts = parse_nm_line(line)
    if 'private' in descriptors: continue
    if len(name_parts) != 3: continue
    mod, name, suffix = name_parts
    if mod != module_name: continue
    if not name.startswith('test'): continue
    if suffix != 'yyF': continue
    yield name_parts[1]


if __name__ == '__main__': main()
