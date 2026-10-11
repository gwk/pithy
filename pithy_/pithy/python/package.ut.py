# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
import subprocess
import sys
from importlib.machinery import EXTENSION_SUFFIXES, ModuleSpec, SourceFileLoader
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pithy.fs import abs_path, make_dirs, make_link
from pithy.path import path_dir, path_join
from pithy.python.package import (find_package_root, qualname_rel_to, resolve_module_in_dirs, resolve_module_installed,
  resolve_spec_paths, SpecResolutionError, walk_module_paths)
from utest import utest, utest_exc, utest_seq, utest_val


this_file = abs_path(__file__)
pithy_py_dir = path_dir(this_file) # pithy_/pithy/py/.
pithy_pkg_dir = path_dir(pithy_py_dir) # pithy_/pithy/ (has py.typed).
proj_dir = path_dir(path_dir(pithy_pkg_dir)) # pithy/ (git root, no py.typed).


with TemporaryDirectory() as tmp:
  # Namespace directories and private sources remain visible, while environments and symlink cycles do not.
  source_names = ('pkg/__init__.py', 'pkg/_private.py', 'pkg/namespace/mod.py')
  skipped_names = ('.hidden/mod.py', 'cache/mod.py', 'env/mod.py', 'pkg/__pycache__/mod.py')
  for name in (*source_names, *skipped_names, 'env/pyvenv.cfg'):
    path = path_join(tmp, name)
    make_dirs(path_dir(path))
    with open(path, 'w') as f: f.write('raise RuntimeError("Do not import while walking.")\n')
  make_link(tmp, link=path_join(tmp, 'pkg/cycle'))
  make_link(path_join(tmp, 'pkg/_private.py'), link=path_join(tmp, 'alias.py'))
  expected = [path_join(tmp, name) for name in source_names]
  # Normalized, overlapping roots must not cause a second visit or duplicate output.
  utest_seq(expected, walk_module_paths, tmp, path_join(tmp, 'pkg/.'), expected[0], exclude_dirs=('cache',))
  # An explicitly requested excluded directory is still scanned.
  utest_seq([path_join(tmp, 'cache/mod.py')], walk_module_paths, path_join(tmp, 'cache'), exclude_dirs=('cache',))


# File in the py subpackage finds the pithy package root.
utest(pithy_pkg_dir, find_package_root, this_file)

# Deeper file in a sub-subpackage.
utest(pithy_pkg_dir, find_package_root, path_join(pithy_py_dir, 'sem', '__init__.py'))

# Directory input: the package root directory itself.
utest(pithy_pkg_dir, find_package_root, pithy_pkg_dir)

# No py.typed found walking up from the git project root.
utest(None, find_package_root, proj_dir)

# package_roots: stops at explicit root before reaching py.typed.
utest(pithy_py_dir, find_package_root, this_file, package_roots={pithy_py_dir})

# package_roots: non-matching entry still finds py.typed.
utest(pithy_pkg_dir, find_package_root, this_file, package_roots={proj_dir})


fixtures_dir = path_join(path_dir(pithy_pkg_dir), 'test', 'python', 'deps', 'fixtures') # pithy_/test/py/deps/fixtures/.
alpha_dir = path_join(fixtures_dir, 'alpha')
alpha_files = [path_join(alpha_dir, name) for name in ('__init__.py', 'base.py', 'mid.py', 'tip.py')]


def fixture_resolver(name:str) -> str|None: return resolve_module_in_dirs(name, [fixtures_dir])


# Plain module and package resolution.
utest(path_join(alpha_dir, 'mid.py'), resolve_module_in_dirs, 'alpha.mid', [fixtures_dir])
utest(path_join(alpha_dir, '__init__.py'), resolve_module_in_dirs, 'alpha', [fixtures_dir])

# Unresolvable and empty names.
utest(None, resolve_module_in_dirs, 'alpha.nonexistent', [fixtures_dir])
utest(None, resolve_module_in_dirs, '', [fixtures_dir])


# A file path spec.
utest([this_file], resolve_spec_paths, this_file)

# A directory path spec walks all Python files.
utest(alpha_files, resolve_spec_paths, alpha_dir)

# A module name spec resolves to a single file.
utest([path_join(alpha_dir, 'tip.py')], resolve_spec_paths, 'alpha.tip', resolve_module=fixture_resolver)

# A package name spec includes all of its submodules.
utest(alpha_files, resolve_spec_paths, 'alpha', resolve_module=fixture_resolver)

# Unresolvable module name.
utest_exc(SpecResolutionError("cannot resolve module 'nonexistent'."), resolve_spec_paths, 'nonexistent',
  resolve_module=fixture_resolver)

# Nonexistent path.
utest_exc(SpecResolutionError("target path not found: 'no/such/dir'"), resolve_spec_paths, 'no/such/dir')


# Sibling subtree within the shared parent package.
utest('.c.d', qualname_rel_to, 'a.b', 'a.c.d')

# Sibling of the containing package requires an extra dot.
utest('..d', qualname_rel_to, 'a.b.c', 'a.d')

# A name within `base` itself gets a single dot (the package interpretation).
utest('.x', qualname_rel_to, 'a.b', 'a.b.x')

# `qual` equal to `base` reduces to a lone dot.
utest('.', qualname_rel_to, 'a.b', 'a.b')

# `qual` is an ancestor package of `base`.
utest('.', qualname_rel_to, 'a.b.c', 'a.b')
utest('..', qualname_rel_to, 'a.b.c', 'a')

# No shared prefix: returned unchanged.
utest('b.c', qualname_rel_to, 'a.x', 'b.c')

# Top-level base.
utest('.b.c', qualname_rel_to, 'a', 'a.b.c')


with TemporaryDirectory() as tmp:
  root = Path(tmp)
  first, second = root / 'first', root / 'second'
  sources = (
    'first/pkg/__init__.py', 'first/pkg/own.py', 'second/pkg/__init__.py', 'second/pkg/child.py',
    'first/choice.py', 'first/choice/__init__.py',
    'first/ns/nested/one.py', 'second/ns/nested/two.py',
    'first/shadow/stray.py', 'second/shadow/__init__.py',
    'first/leaf.py', 'second/leaf/child.py', 'first/native.py', f'first/native{EXTENSION_SUFFIXES[0]}',
  )
  for source in sources:
    source_path = root / source
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text('raise RuntimeError("Target code must not execute.")\n')
  dirs = [str(first), str(second)]
  # Commit to the first regular package, even if a later copy contains the requested child.
  utest(None, resolve_module_in_dirs, 'pkg.child', dirs)
  utest(str(first / 'choice/__init__.py'), resolve_module_in_dirs, 'choice', dirs)
  # Namespace portions combine at each level, but a later regular package shadows them.
  utest(str(first / 'ns/nested/one.py'), resolve_module_in_dirs, 'ns.nested.one', dirs)
  utest(str(second / 'ns/nested/two.py'), resolve_module_in_dirs, 'ns.nested.two', dirs)
  utest(None, resolve_module_in_dirs, 'shadow.stray', dirs)
  utest(None, resolve_module_in_dirs, 'leaf.child', dirs)
  utest(None, resolve_module_in_dirs, 'native', dirs)
  with patch.object(sys, 'path', dirs), patch.dict(os.environ, {'PYTHONSAFEPATH': ''}):
    utest(None, resolve_module_installed, 'pkg.child')
    utest(str(first / 'choice/__init__.py'), resolve_module_installed, 'choice')
    utest(str(second / 'ns/nested/two.py'), resolve_module_installed, 'ns.nested.two')
    utest(None, resolve_module_installed, 'ns')
    utest(None, resolve_module_installed, 'sys')

  class EditableFinder:
    @staticmethod
    def find_spec(fullname:str, path:object=None, target:object=None) -> ModuleSpec|None:
      if fullname not in ('editable', 'choice'): return None
      origin = str(first / 'pkg/__init__.py')
      spec = ModuleSpec(fullname, SourceFileLoader(fullname, origin), origin=origin, is_package=True)
      spec.submodule_search_locations = [str(first / 'pkg')]
      return spec

  with patch.object(sys, 'meta_path', [EditableFinder, *sys.meta_path]):
    utest(str(first / 'pkg/__init__.py'), resolve_module_installed, 'editable', safe_path=True)
    utest(str(first / 'pkg/own.py'), resolve_module_installed, 'editable.own', safe_path=True)
    utest(str(first / 'pkg/__init__.py'), resolve_module_installed, 'choice', safe_path=True)
    utest(None, resolve_module_installed, 'editable.child', safe_path=True)
  utest_val(False, 'editable' in sys.modules)


# Use fresh interpreters to test real startup paths and both CLI flags without mutating this runner's import state.
with TemporaryDirectory() as tmp:
  root = Path(tmp)
  (root / 'localprobe').mkdir()
  (root / 'localprobe/__init__.py').write_text('raise RuntimeError("Package must not execute.")\n')
  (root / 'localprobe/child.py').write_text('raise RuntimeError("Module must not execute.")\n')
  env = dict(os.environ)
  env.pop('PYTHONSAFEPATH', None)
  env.pop('PYTHONPATH', None)
  code = ("import sys; from pithy.python.package import resolve_module_installed; "
    "print(resolve_module_installed('localprobe.child', safe_path=bool(int(sys.argv[1]))) is not None)")
  for python_flags, explicit_safe, safe_env, pythonpath, found_expected in (
    ([], False, '', '', True),
    ([], True, '', '', False),
    ([], False, '1', '', False),
    ([], False, '0', '', False), # Any nonempty value enables Python's safe-path setting.
    (['-P'], False, '', '', False),
    (['-P'], True, '', '', False),
    ([], True, '', tmp, True), # Explicit PYTHONPATH entries must survive removal of the implicit entry.
    ([], False, '1', tmp, True),
    (['-E'], False, '1', '', True),
  ):
    test_env = {**env, 'PYTHONSAFEPATH': safe_env, 'PYTHONPATH': pythonpath}
    result = subprocess.run([sys.executable, *python_flags, '-c', code, str(int(explicit_safe))],
      cwd=tmp, env=test_env, capture_output=True, text=True)
    utest_val((0, f'{found_expected}\n', ''), (result.returncode, result.stdout, result.stderr),
      desc=(python_flags, explicit_safe, safe_env, pythonpath))

  for module in ('summarize', 'deps'):
    for args, safe_env, succeeds in (
      (['localprobe.child'], '', True),
      (['-P', 'localprobe.child'], '', False),
      (['localprobe.child'], '1', False),
      (['-P', 'localprobe'], '', False), # Existing directories must not bypass safe module resolution.
      (['localprobe'], '1', False),
      (['-P', './localprobe'], '', True),
      (['./localprobe'], '1', True),
      (['-P', 'localprobe/child.py'], '', True),
      (['-P', './localprobe', 'localprobe.child'], '', False),
    ):
      result = subprocess.run([sys.executable, '-m', f'pithy.python.{module}', *args], cwd=tmp,
        env={**env, 'PYTHONSAFEPATH': safe_env}, capture_output=True, text=True)
      utest_val(0 if succeeds else 1, result.returncode, desc=(module, args, safe_env, result.stderr))
      if not succeeds:
        utest_val(True, 'cannot resolve module' in result.stderr, desc=result.stderr)
