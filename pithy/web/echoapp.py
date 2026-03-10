# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from .app import WebApp
from .request import Request
from .response import Response


class EchoApp(WebApp):

  def handle_request(self, request:Request) -> Response:
    query = f'?{request.query}' if request.query else ''
    body = f'{request.method}: {request.path}{query}'
    return Response(body=body, media_type='text/plain')


def main() -> None:
  from .server import WebServer
  app = EchoApp()
  server = WebServer(app=app)
  server.serve_forever()


if __name__ == '__main__': main()
