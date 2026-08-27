# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import pithy

from ..reload import DevServerCmd
from ..router import RouterApp
from ..server import ServerConfig, WebServer
from .routes import routes


'''
DevApp is a web app for devolpers to explore the web framework.
For integration tests, see `pithy.web.testapp`.
'''


def main() -> None:
  'Parent process (watcher) entrypoint.'
  DevServerCmd.parse_or_exit().serve(run, watch=[pithy])


def run(config:ServerConfig) -> None:
  'The child process (reloaded) entrypoint.'
  app = DevApp()
  server = WebServer(app=app, config=config)
  server.serve_forever()


class DevApp(RouterApp):

  def __init__(self) -> None:
    super().__init__(routes=routes)



if __name__ == '__main__': main()
