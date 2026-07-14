# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from threading import Thread

from pithy.path import norm_path
from pithy.web.browser import add_browser_args, launch_browser
from pithy.web.files import FilesApp
from pithy.web.server import ServerConfig, WebServer


def main() -> None:

  parser = ArgumentParser(description='Serve files from a directory.')
  parser.add_argument('root', default='.', nargs='?', help='Root directory to serve from.')
  parser.add_argument('-port', default=0, type=int, help='Port to listen on.')
  add_browser_args(parser)

  args = parser.parse_args()

  app = FilesApp(local_dir=norm_path(args.root), prevent_client_caching=True, map_bare_names_to_html=False)
  server = WebServer(app=app, config=ServerConfig(host='localhost', port=args.port))
  server_thread = Thread(target=server.serve_forever)

  server_thread.start()

  if args.browser: launch_browser(server.url, args.browser)

  try:
    server_thread.join()
  except KeyboardInterrupt:
    print('\nKeyboard interrupt received; shutting down server.')
    server.shutdown()
    server_thread.join()
