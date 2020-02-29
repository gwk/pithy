# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# This is the setup.py for for all packages in the repo.
# The package to be installed is selected by copying its setup-PACKAGE.cfg file to setup.cfg.
# This is necessary because pip does not practically allow us to use alternate names for the setup files.

from configparser import ConfigParser
from distutils.command.build_scripts import build_scripts  # type: ignore
from itertools import chain
from os import chmod, environ, getcwd as current_dir, listdir as list_dir, mkdir as make_dir, walk
from os.path import (basename as path_name, dirname as path_dir, exists as path_exists, isdir as is_dir, join as path_join,
  normpath as norm_path, split as split_dir_name, splitext as split_ext)
from pprint import pprint
from typing import Any, List

from setuptools import setup  # type: ignore
from setuptools.command.develop import develop  # type: ignore
from setuptools.command.install import install  # type: ignore
from setuptools.command.install_scripts import install_scripts  # type: ignore
from setuptools.config import read_configuration  # type: ignore


def msg(*items:Any) -> None: print(' ', *items)


# Note: all Command subclasses have the `distribution` property, which in turn has a `metadata` property,
# as well as: packages:List[str]; package_dir:Dict[str,str], py_modules:List[sstr], scripts:List[str] and others.
# See: https://github.com/python/cpython/blob/master/Lib/distutils/dist.py.


class BuildScripts(build_scripts): # type: ignore
  def run(self) -> None:
    super().run()


class Develop(develop): # type: ignore
  def run(self) -> None:
    msg('Develop')
    super().run()
    install_bins(package=self.distribution.metadata.name, dst_dir=self.script_dir)


class Install(install): # type: ignore
  def run(self) -> None:
    msg('Install')
    super().run()


class InstallScripts(install_scripts): # type: ignore
  def run(self) -> None:
    msg('InstallScripts')
    install_bins(package=self.distribution.metadata.name, dst_dir=self.install_dir)


def install_bins(package:str, dst_dir:str) -> None:
  '''
  Generate executable script entry points.
  We do this because standard entry_points/console_scripts have noticeably slow startup times,
  apparently due to overly complex boilerplate.
  '''
  bin_src_dir = path_join(package, 'bin')

  msg('bin_src_dir:', bin_src_dir)
  msg('bin dst_dir:', dst_dir)

  if not is_dir(bin_src_dir):
    msg('note: no bin directory.')
    return
  if not path_exists(dst_dir): make_dir(dst_dir)
  py_path = path_join(dst_dir, 'python3')
  for name in list_dir(bin_src_dir):
    stem, ext = split_ext(name)
    if ext != '.py' or stem.startswith('.') or stem.startswith('_'): continue
    path = path_join(dst_dir, stem.replace('_', '-')) # Omit extension from bin name and use dashes.
    module = f'{package}.bin.{stem}'
    msg(f'generating script: {path}')
    with open(path, 'w') as f:
      f.write(bin_template.format(py_path=py_path, module=module))
      chmod(f.fileno(), 0o755)

bin_template = '''\
#!{py_path}
# Generated by pithy/setup.py.
from {module} import main
main()
'''


def discover_packages(package:str) -> List[str]:
  '''
  Discover subpackages by traversing over the directory tree.
  Verify that all subdirectories have `__init__` files.
  '''
  bad_names = []
  missing_inits = []
  packages = []
  for dir_path, dir_names, file_names in walk(package):
    subpackage_name = dir_path.strip('./').replace('/', '.')
    packages.append(subpackage_name)
    #msg('discovered subpackage:', dir_path, '->', subpackage_name)
    # Filter the subdirectories in place, as permitted by `walk`.
    dir_names[:] = filter(is_subpackage, dir_names)
    # Validate names. Collect them so that we can issue all error messages at once, then exit.
    for name in chain(dir_names, file_names):
      if '-' in name: bad_names.append(path_join(dir_path, name))
    if '__init__.py' not in file_names:
      missing_inits.append(path_join(dir_path, '__init__.py'))

  if bad_names: msg(f'bad module names:\n' + '\n'.join(sorted(bad_names)))
  if missing_inits:
    msg(f'missing package __init__.py files:\n    ' + '\n    '.join(repr(s) for s in sorted(missing_inits)))
  if bad_names or missing_inits: exit(1)
  packages.sort()
  msg('packages:', *packages)
  return packages


def is_subpackage(dir_name:str) -> bool:
  if '.' in dir_name: return False
  if dir_name in ('__pycache__',): return False
  return True


def main() -> None:
  metadata = read_configuration('setup.cfg')['metadata'] # Get the metadata the setuptools way.

  if 'name' not in metadata: exit('error: setup.cfg is missing `name`.')

  name = metadata['name']
  packages = discover_packages(name)
  py_module = name + '.py'
  py_modules = [py_module] if path_exists(py_module) else []

  args = dict(
    license='CC0',
    author='George King',
    author_email='george.w.king@gmail.com',
    url='https://github.com/gwk/pithy',
    include_package_data=True,
    packages=packages,
    cmdclass={
      'build_scripts': BuildScripts,
      'develop': Develop,
      'install': Install,
      'install_scripts': InstallScripts,
    },
    py_modules=py_modules,
    package_dir={name:name},
  )

  #pprint(args)
  setup(**args)


if __name__ == '__main__': main()
