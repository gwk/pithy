# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
from contextlib import redirect_stdout
from io import StringIO
from tempfile import TemporaryDirectory

from crafts.deps import (DepLocation, deps_local_config_trust_problem, DepsConfigError, ensure_dep_symlinks, parse_deps_config,
  parse_deps_local_config, resolve_dep, ResolvedDep, write_deps_local_config)
from utest import utest, utest_exc


utest(('pithy', 'reference'), parse_deps_config, '{"deps": ["pithy", "reference"]}')
utest_exc(DepsConfigError, parse_deps_config, '[]')
utest_exc(DepsConfigError, parse_deps_config, '{"deps": ["a/b"]}')
utest_exc(DepsConfigError, parse_deps_config, '{"deps": ["pithy", "pithy"]}')
utest({'pithy': DepLocation('../../pithy/main')}, parse_deps_local_config, '{"pithy": {"path": "../../pithy/main"}}')
utest({'pithy': DepLocation('../../pithy/main', True)}, parse_deps_local_config,
  '{"pithy": {"path": "../../pithy/main", "writable": true}}')
utest_exc(DepsConfigError, parse_deps_local_config, '{"pithy": "../../pithy/main"}')
utest_exc(DepsConfigError, parse_deps_local_config, '{"pithy": {"path": "../../pithy/main", "writable": 1}}')

with TemporaryDirectory() as temp_dir:
  project_dir = os.path.join(temp_dir, 'project')
  target = os.path.join(temp_dir, 'target')
  os.makedirs(project_dir)
  os.makedirs(target)
  dep = ResolvedDep('source', target)
  utest(dep, resolve_dep, project_dir, 'source', DepLocation('../target'))
  with redirect_stdout(StringIO()): ensure_dep_symlinks(project_dir, [dep])
  utest(target, os.readlink, os.path.join(project_dir, 'deps/source'))
  utest_exc(DepsConfigError, resolve_dep, project_dir, 'missing', DepLocation('../missing'))
  write_deps_local_config(project_dir, {'source': DepLocation('../target', True)})
  utest(None, deps_local_config_trust_problem, project_dir)
  with open(os.path.join(project_dir, '_deps.local.json')) as f:
    utest({'source': DepLocation('../target', True)}, parse_deps_local_config, f.read())
