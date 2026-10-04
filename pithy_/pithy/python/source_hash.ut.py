# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sys
from importlib import import_module
from tempfile import TemporaryDirectory

from pithy.fs import make_dirs
from pithy.path import path_join
from pithy.python.source_hash import loaded_module_paths, program_source_hash
from utest import utest, utest_val, utest_val_ne


pkg = 'source_hash_test_pkg'

def write_pkg(root:str, mod_src:str) -> None:
  make_dirs(path_join(root, pkg))
  for name, src in (('__init__.py', ''), ('mod.py', mod_src)):
    with open(path_join(root, pkg, name), 'w') as f: f.write(src)


with TemporaryDirectory() as tmp_a, TemporaryDirectory() as tmp_b:
  write_pkg(tmp_a, 'x = 1\n')
  sys.path.insert(0, tmp_a)
  try: import_module(f'{pkg}.mod')
  finally: sys.path.remove(tmp_a)

  utest({pkg: path_join(tmp_a, pkg, '__init__.py'), f'{pkg}.mod': path_join(tmp_a, pkg, 'mod.py')}, loaded_module_paths, pkg)

  hash_a = program_source_hash(pkg)
  utest_val(64, len(hash_a), 'SHA-256 hex digest')
  utest(hash_a, program_source_hash, pkg)

  # The hash follows the file contents, including comments.
  write_pkg(tmp_a, 'x = 1 # Comment.\n')
  utest_val_ne(hash_a, program_source_hash(pkg), 'changed source')
  write_pkg(tmp_a, 'x = 1\n')
  utest(hash_a, program_source_hash, pkg)

  # The hash does not depend on the location of the files.
  for name in (pkg, f'{pkg}.mod'): del sys.modules[name]
  write_pkg(tmp_b, 'x = 1\n')
  sys.path.insert(0, tmp_b)
  try: import_module(f'{pkg}.mod')
  finally: sys.path.remove(tmp_b)
  utest(hash_a, program_source_hash, pkg)

  # Without arguments, every loaded module outside of the standard library is selected.
  paths = loaded_module_paths()
  utest_val(True, pkg in paths and 'utest' in paths and 'pithy.python.source_hash' in paths, 'non-stdlib modules')
  utest_val(False, any(name.partition('.')[0] in sys.stdlib_module_names for name in paths), 'stdlib modules')
  utest_val_ne(hash_a, program_source_hash(), 'all modules')

  for name in (pkg, f'{pkg}.mod'): del sys.modules[name]
