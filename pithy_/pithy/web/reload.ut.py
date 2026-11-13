# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sys
from importlib.machinery import ModuleSpec
from os import environ
from os.path import join as path_join, realpath
from tempfile import gettempdir
from types import ModuleType
from unittest.mock import patch

import watchfiles
from pithy.cmdparse import opt
from pithy.web.reload import DevServerCmd, reload_filter, serve_with_reload, target_name
from pithy.web.server import ServerConfig
from utest import utest, utest_exc, utest_run, utest_val


class AppServerCmd(DevServerCmd):
  'A development server with an application-specific option.'
  message:str = opt(default='hello')


def _run(config:ServerConfig) -> None: pass
_run.__module__ = '__main__' # Simulate a function defined in the main module.


def _patch_main(spec_name:str|None) -> ModuleType:
  'Create a stand-in for the `__main__` module, as run by `python -m spec_name` (or without a spec if None).'
  main = ModuleType('__main__')
  main.__spec__ = None if spec_name is None else ModuleSpec(spec_name, loader=None)
  return main


utest(DevServerCmd(port=0, watch=True), DevServerCmd.parse, [])
utest(DevServerCmd(port=8080, watch=False), DevServerCmd.parse, ['-port', '8080', '-no-watch'])
utest(AppServerCmd(port=0, watch=True, message='goodbye'), AppServerCmd.parse, ['-message', 'goodbye'])
utest(ServerConfig(host='localhost', port=1234, prevent_client_caching=True, debug=True),
  lambda: DevServerCmd(port=1234, watch=True).server_config)

utest('pithy.web.reload.serve_with_reload', target_name, serve_with_reload) # A regular module-level function.
utest_exc(ValueError, target_name, lambda config: None)
utest_exc(ValueError, target_name, (lambda: (lambda: None))()) # A nested function.


@utest_run
def _() -> None:
  'A function defined in a `python -m` main module is named via the main module spec.'
  with patch.dict(sys.modules, {'__main__': _patch_main('mypkg.__main__')}):
    utest('mypkg.__main__._run', target_name, _run)


@utest_run
def _() -> None:
  'A function defined in a main module without a spec cannot be named.'
  with patch.dict(sys.modules, {'__main__': _patch_main(None)}):
    utest_exc(ValueError, target_name, _run)


@utest_run
def _() -> None:
  'The reload filter keeps source changes and skips bytecode, isort temporaries and ignored directories.'
  root = realpath(gettempdir())
  static = path_join(root, 'pkg', 'static')
  watch_filter = reload_filter(ignore=[static])
  for path, expected in [
    ('pkg/app.py', True),
    ('pkg/__pycache__/app.cpython-315.pyc', False),
    ('pkg/app.py.isorted', False),
    ('pkg/static/app.js', False),
    ('pkg/static/fixtures/page.html', False),
    ('pkg/static-src/app.py', True), # A sibling sharing the ignored directory's name prefix.
  ]:
    utest(expected, watch_filter, watchfiles.Change.modified, path_join(root, path), _utest_label=repr(path))


@utest_run
def _() -> None:
  'Disabling watch runs the server directly with the local development config.'
  configs:list[ServerConfig] = []
  DevServerCmd(port=4321, watch=False).serve(configs.append, watch=[])
  utest_val([ServerConfig(host='localhost', port=4321, prevent_client_caching=True, debug=True)], configs)


@utest_run
def _() -> None:
  'Watching resolves the port, exports it, and spawns the target by name with the resolved config and ignored paths.'
  static = path_join(realpath(gettempdir()), 'pkg', 'static')
  with (patch.object(watchfiles, 'run_process') as run_process,
        patch.dict(sys.modules, {'__main__': _patch_main('mypkg.__main__')}),
        patch.dict(environ)):
    DevServerCmd(port=0, watch=True).serve(_run, watch=[], ignore=[static], quiet=True)
    (call,) = run_process.call_args_list
    config = call.kwargs['kwargs']['config']
    utest_val('mypkg.__main__._run', call.kwargs['target'])
    utest_val('localhost', config.host)
    utest_val(True, config.port > 0)
    utest_val(True, config.prevent_client_caching)
    utest_val(str(config.port), environ['WEB_PORT'])
    utest(False, call.kwargs['watch_filter'], watchfiles.Change.modified, path_join(static, 'app.js'))
