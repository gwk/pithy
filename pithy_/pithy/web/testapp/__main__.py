# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ..endpoint import Endpoint
from ..router import RouterApp
from ..server import ServerConfig, WebServer
from .basic import EchoId, EchoName, Hello


'''
TestApp is a web app for integration tests.
For various developer demonstrations, see `pithy.web.dev`.
'''


description = 'TestApp web server.'


def main() -> None:
  config = ServerConfig.parse_args(description=description)
  app = TestApp()
  server = WebServer(app=app, config=config)
  server.serve_forever()


class TestApp(RouterApp):

  def __init__(self) -> None:
    super().__init__(routes=routes)


routes:dict[str,type[Endpoint]] = {
  '/': Hello,
  '/items/{id:nat}': EchoId,
  '/users/{name}': EchoName,
}


if __name__ == '__main__': main()
