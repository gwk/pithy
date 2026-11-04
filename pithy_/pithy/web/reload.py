# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Callable, Iterable
from dataclasses import replace
from importlib.resources import files as resource_files
from os import environ, sep as path_sep
from os.path import realpath
from socket import AF_INET, SOCK_STREAM, socket as Socket
from sys import modules as sys_modules
from types import ModuleType
from typing import Any, cast, TYPE_CHECKING

from ..cmdparse import Cmd, flag, opt
from ..io import errL
from .server import ServerConfig


if TYPE_CHECKING: from watchfiles import DefaultFilter


_context_keywords_ = ['development server', 'file watching', 'hot reload', 'multiprocessing spawn', 'port selection',
  'process restart', 'watchfiles']


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

Any change under the watched paths restarts the server, except for bytecode, version control and editor files.
Pass `ignore` to `serve` or `serve_with_reload` to skip directories whose files the server reads afresh on each request,
such as static assets served by `FilesHandler`; edits there take effect on the next request without a restart.
For example, `pithy.web.dev` ignores the pithy and dev static directories.
Files that the server reads only at startup, such as templates or data loaded at import time, must not be ignored.
'''


class DevServerCmd(Cmd):
  '''Common command-line options for a local development server.

  Subclass this command to add application-specific options.
  '''

  port:int = opt(default=0, doc='Port to bind to; 0 selects a free port.')
  watch:bool = flag(default=True, doc='Reload the server when watched source files change (the default); disable with -no-watch.')


  @property
  def server_config(self) -> ServerConfig:
    return ServerConfig(host='localhost', port=self.port, prevent_client_caching=True, debug=True)


  def serve(self, run:Callable[[ServerConfig],None], *, watch:Iterable[str|ModuleType], ignore:Iterable[str]=(),
   quiet:bool=False) -> None:
    '''Run a local server, reloading it by default.

    `run` must be a module-level function taking a ServerConfig.
    When watching is disabled it is called directly;
    otherwise it is spawned in a child process by its qualified name (see `target_name`).
    `ignore` lists directories whose changes do not trigger a reload; see `reload_filter`.
    If `quiet` is true then suppress the reload startup message.
    '''
    config = self.server_config
    if self.watch:
      serve_with_reload(target=target_name(run), watch=watch, ignore=ignore, config=config, quiet=quiet)
    else:
      run(config)


def serve_with_reload(*, target:str, watch:Iterable[str|ModuleType], ignore:Iterable[str]=(), config:ServerConfig|None=None,
 quiet:bool=False) -> None:
  '''
  Spawn a subprocess to run the function named by `target` (a dotted path string) using `watchfiles.run_process`.
  `watch` is an iterable of paths or modules to watch.
  If a module is given, its package path is located and watched.
  The child is restarted whenever a file under any of `watch_paths` changes, except for files excluded by `reload_filter`.

  If `config` is None, a localhost ServerConfig is used.
  If the port is 0, a free port is picked and set in the config so that successive child processes reuse it.
  The resolved config is passed to `target` as the `config` keyword argument.
  `$WEB_PORT` is also exported before spawning for the benefit of other tooling.
  '''
  from watchfiles import run_process

  if config is None: config = ServerConfig(host='localhost')
  if not config.port: config = replace(config, port=_pick_free_port())
  environ['WEB_PORT'] = str(config.port)

  watch_paths = [_resolve_watch(w) for w in watch]
  if not quiet: errL(f'Serving port {config.port}; watching {watch_paths!r}.')

  def _watch_callback(changes:set[tuple[Any,str]]) -> None:
    changed_files = sorted(path for _change, path in changes)
    msg = f'Changes detected: {changed_files}'
    errL(msg)

  run_process(*watch_paths, target=target, target_type='function', kwargs={'config': config},
    watch_filter=reload_filter(ignore), callback=_watch_callback)


def reload_filter(ignore:Iterable[str]=()) -> DefaultFilter:
  '''
  Return the watch filter used by `serve_with_reload`.

  It extends the watchfiles `DefaultFilter`, which skips bytecode, version control and editor files,
  to also skip isort's `.isorted` temporaries and every file under the `ignore` directories.
  Ignore directories whose files the server reads on each request, such as static assets served by `FilesHandler`.
  Do not ignore files that the server reads only at startup; the server would keep serving stale content.
  '''
  from watchfiles import DefaultFilter

  # watchfiles matches ignore paths as string prefixes against the real paths it reports; the trailing separator
  # prevents a directory from also matching its siblings with the same prefix.
  return DefaultFilter(ignore_entity_patterns=(*DefaultFilter.ignore_entity_patterns, r'\.isorted$'),
    ignore_paths=[realpath(path).rstrip(path_sep) + path_sep for path in ignore])


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
