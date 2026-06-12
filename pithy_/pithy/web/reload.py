# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Iterable
from importlib.resources import files as resource_files
from os import environ
from socket import AF_INET, SOCK_STREAM, socket as Socket
from types import ModuleType
from typing import Any, cast

from ..io import errL
from .server import ServerConfig


'''
Hot-reload helper for pithy.web servers.

Wraps `watchfiles.run_process` to respawn a child process whenever files under the watched paths change.
If a port is not specified by `-port` or `$WEB_PORT` then one is chosen and exported as `$WEB_PORT`
so that the child rebinds the same port across reloads.

Typical usage in an app's `__main__.py`:


  import mypkg
  import pithy
  from pithy.web.reload import serve_with_reload
  from pithy.web.server import ServerConfig, WebServer

  description = 'MyApp web server.'

  def main() -> None:
    serve_with_reload(
      target=f'{__package__}.__main__.run',
      watch=[mypkg, pithy],
      description=description)

  def run() -> None:
    config = ServerConfig.parse_args(description=description)
    WebServer(app=mypkg.MyApp(), config=config).serve_forever()

  if __name__ == '__main__': main()
'''


def serve_with_reload(*, target:str, watch:Iterable[str|ModuleType], config:ServerConfig|None=None,
 description:str='Web server configuration.') -> None:
  '''
  Spawn a subprocess to run the function named by `target` (a dotted path string) using `watchfiles.run_process`.
  `watch` is an iterable of paths or modules to watch.
  If a module is given, its package path is located and watched.
  The child is restarted whenever a file under any of `watch_paths` changes.

  If `config` is None, `ServerConfig.parse_args(description=description)` is called.
  If the resulting port is 0, a free port is picked so that successive child processes reuse it.
  `$WEB_PORT` is exported before spawning so that the child observes the same port.
  '''
  from watchfiles import Change, run_process

  if config is None: config = ServerConfig.parse_args(description=description)
  port = config.port or _pick_free_port()
  environ['WEB_PORT'] = str(port) # The child process inherits this and rebinds the same port.

  watch_paths = [_resolve_watch(w) for w in watch]
  errL(f'Serving port {port}; watching {watch_paths!r}.')

  def _watch_filter(change:Change, path:str) -> bool:
    return not path.endswith('.isorted')

  def _watch_callback(changes:set[tuple[Any,str]]) -> None:
    changed_files = sorted(path for _change, path in changes)
    msg = f'Changes detected: {changed_files}'
    errL(msg)

  run_process(*watch_paths, target=target, target_type='function', watch_filter=_watch_filter, callback=_watch_callback)



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
