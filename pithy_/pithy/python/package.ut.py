# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.fs import abs_path
from pithy.path import path_dir, path_join
from pithy.python.package import (find_package_root, qualname_rel_to, resolve_module_in_dirs, resolve_spec_paths,
  SpecResolutionError)
from utest import utest, utest_exc


this_file = abs_path(__file__)
pithy_py_dir = path_dir(this_file) # pithy_/pithy/py/.
pithy_pkg_dir = path_dir(pithy_py_dir) # pithy_/pithy/ (has py.typed).
proj_dir = path_dir(path_dir(pithy_pkg_dir)) # pithy/ (git root, no py.typed).


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
