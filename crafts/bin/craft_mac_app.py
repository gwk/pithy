# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-mac-app` is an experimental build tool that builds a complete mac app without using Xcode.
The steps to build a functioning app were discovered by looking at the raw build logs in an Xcode application.
This is not currently in use and may need updating.
'''

import plistlib
import re
from argparse import ArgumentParser, Namespace
from typing import Any, BinaryIO

from crafts import CraftConfig, load_craft_config
from pithy.filestatus import file_mtime, file_mtime_or_zero
from pithy.fs import copy_path, make_dirs, path_dir, path_exists, walk_files
from pithy.io import outSL, shell_cmd_str
from pithy.path import norm_path, path_join
from pithy.string import replace_prefix
from pithy.task import run, runO


def main() -> None:
  arg_parser = ArgumentParser(description='Build Mac Swift apps using the Swift Package Manager (without Xcode).')
  args = arg_parser.parse_args()

  conf = load_craft_config()

  build(args, conf)


def build(args:Namespace, conf:CraftConfig) -> None:
  build_dir = conf.build_dir
  sources = conf.sources

  for source in sources:
    if not path_exists(source, follow=True):
      exit(f'craft error: source does not exist: {source!r}')

  #sdk_dir = f'{dev_dir}/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk' # The versioned SDK just links to the unversioned one.
  mode_dir = f'{build_dir}/debug' # TODO: support other modes/configurations.

  # Build program.
  run(['craft-swift'], exits=1)

  # Bundle paths.
  bundle_path = f'{mode_dir}/{conf.product_name}.app'
  contents_path = bundle_path + '/Contents'
  frameworks_path = contents_path + '/Frameworks'
  macos_path = contents_path + '/MacOS'
  resources_path = contents_path + '/Resources'

  # Make directories.
  for path in (bundle_path, contents_path, frameworks_path, macos_path, resources_path):
    make_dirs(path)

  # Copy executable.
  exe_src = f'{mode_dir}/{conf.product_name}'
  exe_dst = f'{macos_path}/{conf.product_name}'
  copy_path(exe_src, exe_dst)

  # Compile image assets.
  img_deps_path = f'{mode_dir}/image-deps.txt'
  img_info_path = f'{mode_dir}/icon.plist'
  actool_cmd = [ 'xcrun', 'actool',
    '--output-format', 'human-readable-text',
    #'--notices',
    '--warnings',
    '--export-dependency-info', img_deps_path,
    '--output-partial-info-plist', img_info_path,
    '--app-icon', 'AppIcon',
    '--enable-on-demand-resources', 'NO',
    '--target-device', 'mac',
    '--minimum-deployment-target', conf.target_macOS,
    '--platform', 'macosx',
    '--product-type', 'com.apple.product-type.application',
    '--compile', resources_path,
    'images.xcassets']

  _ = runO(actool_cmd, exits=True) # output is not helpful.
  #img_deps = open(img_deps_path).read()
  img_info:dict[str,Any] = plistlib.load(open(img_info_path, 'rb'))
  #errL('img_deps:\n', img_deps, '\n')
  #errP('img_info', img_info)

  # Generate Info.plist.
  plist_path = f'{contents_path}/Info.plist'
  with open(plist_path, 'wb') as f:
    gen_plist(f,
      EXECUTABLE_NAME=conf.product_name,
      PRODUCT_BUNDLE_IDENTIFIER=conf.product_identifier,
      PRODUCT_NAME=conf.product_name,
      MACOSX_DEPLOYMENT_TARGET=conf.target_macOS,
      copyright=conf.copyright,
      principle_class='NSApplication',
      **img_info)

  # Copy frameworks.

  # Copy resources.
  for res_root, dst_root in conf.resources.items():
    build_dst_root = path_join(build_dir, dst_root)
    for res_path in walk_files(res_root):
      dst_path = norm_path(replace_prefix(res_path, prefix=res_root, replacement=build_dst_root))
      res_mtime = file_mtime(res_path, follow=True)
      dst_mtime = file_mtime_or_zero(dst_path, follow=True)
      if res_mtime == dst_mtime: continue
      outSL(res_path, '->', dst_path)
      if res_mtime < dst_mtime: exit(f'resource build copy was subsequently modified: {dst_path}')
      make_dirs(path_dir(dst_path))
      copy_path(res_path, dst_path)

  # Touch the bundle.
  run(['touch', '-c', bundle_path], exits=True)

  # TODO: register with launch services?


def gen_plist(dst_file:BinaryIO, EXECUTABLE_NAME:str|None, PRODUCT_BUNDLE_IDENTIFIER:str|None,
 PRODUCT_NAME:str|None, MACOSX_DEPLOYMENT_TARGET:str, copyright:str, principle_class:str, **items:str) -> None:
  d = {
    'BuildMachineOSBuild': '17A362a', # TODO.
    'CFBundleDevelopmentRegion': 'en',
    'CFBundleExecutable': EXECUTABLE_NAME,
    'CFBundleIdentifier': PRODUCT_BUNDLE_IDENTIFIER,
    'CFBundleInfoDictionaryVersion': '6.0',
    'CFBundleName': PRODUCT_NAME,
    'CFBundlePackageType': 'APPL',
    'CFBundleShortVersionString': '1.0', # TODO.
    'CFBundleSignature': '????',
    'CFBundleSupportedPlatforms': ['MacOSX'],
    'CFBundleVersion': '1', # TODO.
    'DTCompiler': 'com.apple.compilers.llvm.clang.1_0', # TODO.
    'DTPlatformBuild': '9A235', # TODO.
    'DTPlatformVersion': 'GM', # TODO.
    'DTSDKBuild': '17A360', # TODO.
    'DTSDKName': 'macosx10.15', # TODO.
    'DTXcode': '0900', # TODO.
    'DTXcodeBuild': '9A235', # TODO.
    'LSMinimumSystemVersion': MACOSX_DEPLOYMENT_TARGET,
    'NSHumanReadableCopyright': copyright,
    'NSPrincipalClass': principle_class,
    **items
  }
  plistlib.dump(d, dst_file)


def detect_swift_imports(swift_source_paths:list[str]) -> list[str]:
  # Prior to swift 5 it was necessary to copy swift libs into the app.
  # This is not currently used but we are hanging onto it for now.
  egrep_cmd = ['egrep', '--no-filename', '--only-matching', r'\s*import .*'] + swift_source_paths
  print(shell_cmd_str(egrep_cmd))
  swift_import_lines = list(filter(None, runO(egrep_cmd).split('\n'))) # TODO: use run_gen.
  return sorted(set(trim_import_statement(line) for line in swift_import_lines))


def trim_import_statement(statement:str) -> str:
  m = re.match(r'\s*import (\w+)', statement)
  if not m: raise ValueError(f'egrep found bad import line: {statement!r}')
  return m[1]


if __name__ == '__main__': main()
