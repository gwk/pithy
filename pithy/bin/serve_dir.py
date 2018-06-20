# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from functools import partial
from ..http.server import HTTPServer, HTTPRequestHandler
from ..task import run

def main():

  from argparse import ArgumentParser

  parser = ArgumentParser(description='Serve files from a directory.')
  parser.add_argument('root', default='.', nargs='?', help='Root directory to serve from')
  parser.add_argument('-browse', action='store_true', help='Launch the default system browser')
  parser.add_argument('-safari',  action='store_true', help='Launch Safari')
  parser.add_argument('-chrome',  action='store_true', help='Launch Google Chrome')
  parser.add_argument('-firefox', action='store_true', help='Launch Firefox')

  args = parser.parse_args()
  root = args.root
  address = ('localhost', 8000) # TODO: argparse option.
  host, port = address
  addr_str = f'http://{host}:{port}'
  print(addr_str)

  ignored_paths = {
    'apple-touch-icon-precomposed.png',
  }

  server = HTTPServer(address, partial(HTTPRequestHandler, directory=root))

  # note: the way we tell the OS to open the URL in the browser is a rather suspicious hack:
  # the `open` command returns and then we launch the web server,
  # relying on the fact that together the OS and the launched browser take more time to initiate the request
  # after the `open` process completes than the server does to initialize.
  if args.browse:   run(['open', addr_str])
  if args.safari:   run(['open', '-a', 'safari',        addr_str])
  if args.chrome:   run(['open', '-a', 'google chrome', addr_str])
  if args.firefox:  run(['open', '-a', 'firefox',       addr_str])

  try: server.serve_forever()
  except KeyboardInterrupt:
    print('\nKeyboard interrupt received; shutting down server.')
    exit()
