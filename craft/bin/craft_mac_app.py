# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
import os.path
import plistlib
import re
from argparse import ArgumentParser
from pithy.ansi import *
from pithy.io import *
from pithy.fs import copy_path, path_exists, make_dirs
from pithy.string import find_and_clip_suffix, replace_prefix
from pithy.task import *
from craft import *


def main() -> None:
  arg_parser = ArgumentParser(description='Build Mac Swift apps using the Swift Package Manager (without Xcode).')
  args = arg_parser.parse_args()

  conf = load_craft_config()
  package = update_swift_package_json(conf)

  build(args, conf, package)


def build(args, conf, package):
  build_dir = conf.build_dir
  sources = conf.sources

  for source in sources:
    if not path_exists(source):
      exit(f'craft error: source does not exist: {source!r}')

  dev_dir = find_dev_dir()

  sdk_dir = f'{dev_dir}/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk' # The versioned SDK just links to the unversioned one.
  #swift_libs_dir = f'{conf.xcode_toolchain_dir}/lib/swift/macosx'
  swift_libs_dir = f'{dev_dir}/Toolchains/XcodeDefault.xctoolchain/usr/lib/swift/macosx'
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
  img_deps = open(img_deps_path).read()
  img_info = plistlib.load(open(img_info_path, 'rb'))
  #errL('img_deps:\n', img_deps, '\n')
  #errP(img_info, label='img_info')

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

  # Find swift source paths.
  swift_source_paths = sorted(walk_files(*sources, file_exts=['.swift']))

  # Detect swift imports.
  egrep_cmd = ['egrep', '--no-filename', '--only-matching', r'\s*import .*'] + swift_source_paths
  swift_import_lines = list(filter(None, runO(egrep_cmd).split('\n'))) # TODO: use run_gen.
  swift_imports = sorted(set(trim_import_statement(line) for line in swift_import_lines))

  # Copy swift libs.
  swift_libs = set(required_libs)
  swift_libs.update(debug_libs)
  swift_libs.update(swift_imports)

  for import_name in swift_imports:
    if import_name in system_frameworks:
      lib_name = f'libswift{import_name}.dylib'
      src_path = f'{swift_libs_dir}/{lib_name}'
      dst_path = f'{frameworks_path}/{lib_name}'
      if not path_exists(dst_path):
        copy_path(src_path, dst_path)
    else:
      pass
      #errSL('note: ignoring unknown import:', import_name)

  # Copy frameworks.

  # Copy resources.
  for res_root, dst_root in conf.resources.items():
    build_dst_root = path_join(build_dir, dst_root)
    for res_path in walk_files(res_root):
      dst_path = norm_path(replace_prefix(res_path, prefix=res_root, replacement=build_dst_root))
      res_mtime = file_time_mod(res_path)
      dst_mtime = file_time_mod_or_zero(dst_path)
      if res_mtime == dst_mtime: continue
      outSL(res_path, '->', dst_path)
      if res_mtime < dst_mtime: exit(f'resource build copy was subsequently modified: {dst_path}')
      make_dirs(path_dir(dst_path))
      copy_path(res_path, dst_path)

  # Touch the bundle.
  run(['touch', '-c', bundle_path], exits=True)

  # TODO: register with launch services?


def gen_plist(dst_file, EXECUTABLE_NAME, PRODUCT_BUNDLE_IDENTIFIER, PRODUCT_NAME, MACOSX_DEPLOYMENT_TARGET, copyright, principle_class, **items):
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
    'DTSDKName': 'macosx10.13', # TODO.
    'DTXcode': '0900', # TODO.
    'DTXcodeBuild': '9A235', # TODO.
    'LSMinimumSystemVersion': MACOSX_DEPLOYMENT_TARGET,
    'NSHumanReadableCopyright': copyright,
    'NSPrincipalClass': principle_class,
    **items
  }
  plistlib.dump(d, dst_file)


def trim_import_statement(statement):
  m = re.match(r'\s*import (\w+)', statement)
  if not m: raise ValueError(f'egrep found bad import line: {statement!r}')
  return m[1]


system_frameworks = {
  'AVFoundation',
  'Accelerate',
  'AppKit',
  'CloudKit',
  'Contacts',
  'Core',
  'CoreAudio',
  'CoreData',
  'CoreFoundation',
  'CoreGraphics',
  'CoreImage',
  'CoreLocation',
  'CoreMedia',
  'CryptoTokenKit',
  'Darwin',
  'Dispatch',
  'Foundation',
  'GLKit',
  'GameplayKit',
  'IOKit',
  'Intents',
  'MapKit',
  'Metal',
  'MetalKit',
  'ModelIO',
  'ObjectiveC',
  'OpenCL',
  'QuartzCore',
  'RemoteMirror',
  'SafariServices',
  'SceneKit',
  'SpriteKit',
  'SwiftOnoneSupport',
  'Vision',
  'XCTest',
  'XPC',
  'os',
  'simd',
}

required_libs = { # TODO: unsure about this.
  'os',
  'ObjectiveC'
}

debug_libs = { # TODO: release libs.
  'RemoteMirror', # TODO: necessary?
  'SwiftOnoneSupport'
}


if __name__ == '__main__': main()
