# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import pithy

from ...cmdparse import Cmd, flag, opt
from ...web.reload import serve_with_reload
from ...web.server import ServerConfig, WebServer
from ._webtest import ChartTestApp


class ChartTestCmd(Cmd):
  'Serve the pithy.html.charts test page.'

  port:int = opt(default=0, doc='Port to bind to; 0 selects a free port.')
  watch:bool = flag(default=True, doc='Reload the server when pithy source files change.')


def main() -> None:
  cmd = ChartTestCmd.parse_or_exit()
  config = ServerConfig(host='localhost', port=cmd.port)
  if cmd.watch:
    serve_with_reload(target=f'{__package__}.__main__.run', watch=[pithy], config=config)
  else:
    run(config)


def run(config:ServerConfig|None=None) -> None:
  WebServer(app=ChartTestApp(), config=config or ServerConfig(host='localhost')).serve_forever()


if __name__ == '__main__': main()
