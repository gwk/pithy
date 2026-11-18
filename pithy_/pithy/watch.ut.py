# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os.path import join as path_join, realpath
from tempfile import gettempdir

import watchfiles
from pithy.watch import watch_filter
from utest import utest, utest_run


@utest_run
def _() -> None:
  'The filter keeps source changes and skips bytecode, isort temporaries and ignored directories.'
  root = realpath(gettempdir())
  static = path_join(root, 'pkg', 'static')
  filter = watch_filter(ignore=[static])
  for path, expected in [
    ('pkg/app.py', True),
    ('pkg/__pycache__/app.cpython-315.pyc', False),
    ('pkg/app.py.isorted', False),
    ('pkg/static/app.js', False),
    ('pkg/static/fixtures/page.html', False),
    ('pkg/static-src/app.py', True), # A sibling sharing the ignored directory's name prefix.
  ]:
    utest(expected, filter, watchfiles.Change.modified, path_join(root, path), _utest_label=repr(path))
