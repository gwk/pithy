# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from sys import argv, stdin
from typing import BinaryIO

from ..task import run


def main() -> None:

  parser = ArgumentParser(description='Serve a file or `stdin` to a browser.')
  parser.add_argument('-chrome',  action='store_true', help='Use Google Chrome')
  parser.add_argument('-firefox', action='store_true', help='Use Firefox')
  parser.add_argument('-safari',  action='store_true', help='Use Safari')
  parser.add_argument('-stp',  action='store_true', help='Use Safari Technology Preview')
  parser.add_argument('path', nargs='?', help='The file path to serve (defaults to stdin).')
  args = parser.parse_args()

  address = ('localhost', 8000) # TODO: argparse option.
  host, port = address
  addr_str = f'http://{host}:{port}'

  f:BinaryIO
  if args.path is not None:
    f = open(args.path, 'rb')
  else:
    f = stdin.detach() # type: ignore


  class Handler(BaseHTTPRequestHandler):

    def do_HEAD(self):
      self.send_response(200)
      self.send_header('Content-Type', 'text/html')
      self.end_headers()

    def do_GET(self):
      self.send_response(200)
      self.send_header('Content-Type', 'text/html')
      self.end_headers()
      for line in f:
        self.wfile.write(line)
        self.wfile.flush()


  server = HTTPServer(address, Handler)

  # note: the way we tell the OS to open the URL in the browser is a rather suspicious hack:
  # the `open` command returns and then we launch the web server,
  # relying on the fact that together the OS and the launched browser take more time to initiate the request
  # after the `open` process completes than the server does to initialize.
  if args.chrome:     run(['open', '-a', 'google chrome', addr_str])
  elif args.firefox:  run(['open', '-a', 'firefox',       addr_str])
  elif args.safari:   run(['open', '-a', 'safari',        addr_str])
  elif args.stp:      run(['open', '-a', 'safari technology preview', addr_str])
  else:               run(['open', addr_str])

  server.handle_request()


if __name__ == '__main__': main()
