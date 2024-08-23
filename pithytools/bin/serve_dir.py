# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from threading import Thread

from pithy.http.server import HttpServer, Response
from pithy.web.app import Request, WebApp
from pithy.web.browser import add_browser_args, launch_browser


def main() -> None:

  parser = ArgumentParser(description='Serve files from a directory.')
  parser.add_argument('root', default='.', nargs='?', help='Root directory to serve from')
  parser.add_argument('-port', default=8000, type=int, help='Port to listen on')
  add_browser_args(parser, add_browse=True)
  args = parser.parse_args()

  root = args.root
  host = 'localhost'
  port = args.port
  #address = (host, port)
  addr_str = f'http://{host}:{port}'
  print(f'Serving {root!r} on {addr_str}…')

  #ignored_paths = { 'apple-touch-icon-precomposed.png' }

  app = LocalFileApp(local_dir=root, prevent_client_caching=True, map_bare_names_to_html=False)
  server = HttpServer(host=host, port=port, app=app)
  server_thread = Thread(target=server.serve_forever)

  server_thread.start()

  if args.browser: launch_browser(addr_str, args.browser)

  try:
    server_thread.join()
  except KeyboardInterrupt:
    print('\nKeyboard interrupt received; shutting down server.')
    exit()


class LocalFileApp(WebApp):

  def handle_request(self, request:Request) -> Response:
    request.allow_methods('GET')
    return self.serve_content_from_local_fs(request)
