# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.fs import abs_path
from pithy.path import path_dir, path_join
from pithy.python.deps import default_universe, DepsError
from pithy.python.package import resolve_module_in_dirs
from utest import utest, utest_exc


pithy_dir = path_dir(path_dir(path_dir(abs_path(__file__)))) # pithy_/, the intermediate directory containing the package.
fixtures_dir = path_join(pithy_dir, 'test', 'python', 'deps', 'fixtures')
alpha_dir = path_join(fixtures_dir, 'alpha')


def fixture_resolver(name:str) -> str|None: return resolve_module_in_dirs(name, [fixtures_dir])


# The default universe is the top-level package directory of the longest resolvable module prefix of the spec.
utest(alpha_dir, default_universe, 'alpha', resolve_module=fixture_resolver)
utest(alpha_dir, default_universe, 'alpha.base', resolve_module=fixture_resolver)
utest(alpha_dir, default_universe, 'alpha.base.CONST', resolve_module=fixture_resolver)
utest(alpha_dir, default_universe, 'alpha.mid.Mid.value', resolve_module=fixture_resolver)

utest_exc(DepsError("cannot resolve module for 'nonexistent.sym'; give targets explicitly."), default_universe, 'nonexistent.sym',
  resolve_module=fixture_resolver)
