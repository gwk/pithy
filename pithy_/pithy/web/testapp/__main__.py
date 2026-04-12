# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from . import TestApp


def main() -> None:
  from ..server import WebServer
  app = TestApp()
  server = WebServer(app=app)
  server.serve_forever()


if __name__ == '__main__': main()
