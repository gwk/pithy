# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Callable, Iterable
from dataclasses import replace
from importlib.resources import files as resource_files
from os import environ
from socket import AF_INET, SOCK_STREAM, socket as Socket
from sys import modules as sys_modules
from types import ModuleType
from typing import Any, cast

from ..cmdparse import Cmd, flag, opt
from ..io import errL
from .server import ServerConfig


'''
Developer command and hot-reload helper for pithy.web servers.

Wraps `watchfiles.run_process` to respawn a child process whenever files under the watched paths change.
If a port is not specified by `-port` or `$WEB_PORT` then a free one is chosen,
and the resolved ServerConfig is passed to the child so that it rebinds the same port across reloads.
The port is also exported as `$WEB_PORT` for the benefit of other tooling.

Typical usage in an app's `__main__.py`:


  import mypkg
  import pithy
  from pithy.web.reload import DevServerCmd
  from pithy.web.server import ServerConfig, WebServer

  def main() -> None:
    DevServerCmd.parse_or_exit().serve(run, watch=[mypkg, pithy])

  def run(config:ServerConfig) -> None:
    WebServer(app=mypkg.MyApp(), config=config).serve_forever()

  if __name__ == '__main__': main()
'''


class DevServerCmd(Cmd):
  '''Common command-line options for a local development server.

  Subclass this command to add application-specific options.
  '''

  port:int = opt(default=0, doc='Port to bind to; 0 selects a free port.')
  watch:bool = flag(default=True, doc='Reload the server when watched source files change.')


  @property
  def server_config(self) -> ServerConfig:
    return ServerConfig(host='localhost', port=self.port)


  def serve(self, run:Callable[[ServerConfig],None], *, watch:Iterable[str|ModuleType]) -> None:
    '''Run a local server, reloading it by default.

    `run` must be a module-level function taking a ServerConfig.
    When watching is disabled it is called directly;
    otherwise it is spawned in a child process by its qualified name (see `target_name`).
    '''
    config = self.server_config
    if self.watch:
      serve_with_reload(target=target_name(run), watch=watch, config=config)
    else:
      run(config)


def serve_with_reload(*, target:str, watch:Iterable[str|ModuleType], config:ServerConfig|None=None) -> None:
  '''
  Spawn a subprocess to run the function named by `target` (a dotted path string) using `watchfiles.run_process`.
  `watch` is an iterable of paths or modules to watch.
  If a module is given, its package path is located and watched.
  The child is restarted whenever a file under any of `watch_paths` changes.

  If `config` is None, a localhost ServerConfig is used.
  If the port is 0, a free port is picked and set in the config so that successive child processes reuse it.
  The resolved config is passed to `target` as the `config` keyword argument.
  `$WEB_PORT` is also exported before spawning for the benefit of other tooling.
  '''
  from watchfiles import Change, run_process

  if config is None: config = ServerConfig(host='localhost')
  if not config.port: config = replace(config, port=_pick_free_port())
  environ['WEB_PORT'] = str(config.port)

  watch_paths = [_resolve_watch(w) for w in watch]
  errL(f'Serving port {config.port}; watching {watch_paths!r}.')

  def _watch_filter(change:Change, path:str) -> bool:
    return not path.endswith('.isorted')

  def _watch_callback(changes:set[tuple[Any,str]]) -> None:
    changed_files = sorted(path for _change, path in changes)
    msg = f'Changes detected: {changed_files}'
    errL(msg)

  run_process(*watch_paths, target=target, target_type='function', kwargs={'config': config},
    watch_filter=_watch_filter, callback=_watch_callback)



def target_name(fn:Callable[...,Any]) -> str:
  '''
  Return the importable dotted name of a module-level function, suitable as a `watchfiles.run_process` target.

  A function object cannot be passed to the child directly:
  the typical `run` lives in a package `__main__` module, which multiprocessing's spawn bootstrap deliberately
  does not re-import in the child, so a pickled reference to `__main__.run` would fail to resolve.
  Instead, the real module name is recovered from `sys.modules['__main__'].__spec__` (as set by `python -m`),
  and the child imports the module by that name, under which `if __name__ == '__main__'` guards do not fire.
  '''
  module_name = fn.__module__
  qualname = fn.__qualname__
  if '<locals>' in qualname or '<lambda>' in qualname:
    raise ValueError(f'reload target must be a module-level function: {fn!r}')
  if module_name == '__main__':
    spec = sys_modules['__main__'].__spec__
    if spec is None:
      raise ValueError(f'reload target is defined in __main__ but the main module has no spec; run it with `python -m`: {fn!r}')
    module_name = spec.name
  return f'{module_name}.{qualname}'


def _pick_free_port() -> int:
  # There is a small TOCTOU race between close and the child's bind() call; acceptable for dev hot-reload.
  with Socket(AF_INET, SOCK_STREAM) as s:
    s.bind(('', 0))
    return cast(int, s.getsockname()[1])


def _resolve_watch(path_or_module:str|ModuleType) -> str:
  'Return a resource path for argument.'
  if isinstance(path_or_module, str): return path_or_module
  module = path_or_module
  if pkg := getattr(module, '__package__', ''):
    return str(resource_files(pkg))
  if file := getattr(module, '__file__', ''):
    return file
  raise ValueError(f'Cannot determine path for module {module!r}.')
