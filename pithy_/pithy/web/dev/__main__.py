# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import pithy

from ..reload import serve_with_reload
from ..router import Router, RouterApp
from ..server import ServerConfig, WebServer
from .routes import routes


'''
DevApp is a web app for devolpers to explore the web framework.
For integration tests, see `pithy.web.testapp`.
'''


description = 'DevApp web server.'


def main() -> None:
  'Parent process (watcher) entrypoint.'
  serve_with_reload(
    target=f'{__package__}.__main__.run',
    watch=[pithy],
    description=description)


def run() -> None:
  'The child process (reloaded) entrypoint.'
  config = ServerConfig.parse_args(description=description)
  app = DevApp()
  server = WebServer(app=app, config=config)
  server.serve_forever()


class DevApp(RouterApp):

  def __init__(self) -> None:
    super().__init__(router=Router(routes))



if __name__ == '__main__': main()
