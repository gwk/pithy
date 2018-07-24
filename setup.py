# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from distutils.command.build_scripts import build_scripts
from itertools import chain
from os import chmod, getcwd, listdir, walk as walk_path
from os.path import join as path_join, splitext as split_ext
from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install
from sys import stderr


bin_src_dirs = ['legs/bin']

def errSL(*items): print(*items, file=stderr)

class Develop(develop):
  def run(self):
    super().run()
    gen_bins(bin_dst_dir=self.script_dir)

class Install(install):
  def run(self):
    super().run()
    gen_bins(bin_dst_dir=self.install_scripts)

def gen_bins(*, bin_dst_dir:str) -> None:
  errSL('bin_dst_dir:', bin_dst_dir)
  assert bin_dst_dir.startswith('/'), bin_dst_dir
  py_path = path_join(bin_dst_dir, 'python3')
  for src_dir in bin_src_dirs:
    for name in listdir(src_dir):
      stem, ext = split_ext(name)
      if stem[0] in '._' or ext != '.py': continue
      path = path_join(bin_dst_dir, stem.replace('_', '-')) # Omit extension from bin name.
      module = path_join(src_dir, stem).replace('/', '.')
      errSL(f'generating script for {module}: {path}')
      with open(path, 'w') as f:
        f.write(bin_template.format(py_path=py_path, module=module))
        chmod(f.fileno(), 0o755)

bin_template = '''\
#!{py_path}
# Generated by legs/setup.py.
from {module} import main
main()
'''


setup(
  cmdclass={
    'develop': Develop,
    'install': Install,
  },
  packages=['legs'],
  package_data={'legs': [
    'swift_base.swift'
  ]},
  py_modules=['legs_base'],
  install_requires=[
    'pithy',
    'unico',
  ],
)
