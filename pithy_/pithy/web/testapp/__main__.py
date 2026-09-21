# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import pithy

from ..reload import DevServerCmd
from ..router import RouterApp, RouteTarget
from ..server import ServerConfig, WebServer
from .basic import echo_id, echo_name, EchoBody, hello


'''
TestApp is a web app for integration tests.
For various developer demonstrations, see `pithy.web.dev`.
'''


def main() -> None:
  DevServerCmd.parse_or_exit().serve(run, watch=[pithy])


def run(config:ServerConfig) -> None:
  app = TestApp()
  server = WebServer(app=app, config=config)
  server.serve_forever()


class TestApp(RouterApp):

  def __init__(self) -> None:
    super().__init__(routes=routes)


routes:dict[str,RouteTarget] = {
  '/': hello,
  '/items/{id:nat}': echo_id,
  '/users/{name}': echo_name,
  '/echo': EchoBody,
}


if __name__ == '__main__': main()
