# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser, FileType
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import BinaryIO

from pithy.web.browser import add_browser_args, launch_browser


def main() -> None:

  parser = ArgumentParser(description='Serve a file or `stdin` to a browser.')
  parser.add_argument('-port', type=int, default=8000, help='The port to serve on.')
  parser.add_argument('file', nargs='?', type=FileType('rb'), default='-', help='The file path to serve (defaults to stdin).')

  add_browser_args(parser)
  args = parser.parse_args()

  address = ('localhost', args.port)
  host, port = address
  addr_str = f'http://{host}:{port}'

  f_in:BinaryIO = args.file
  print(f'Serving {f_in.name} on {addr_str}.')

  server_thread = ServerThread(address, f_in)
  server_thread.start()

  launch_browser(addr_str, args.browser)
  server_thread.join()


class ServerThread(Thread):

  def __init__(self, address:tuple[str,int], f_in:BinaryIO) -> None:

    class Handler(BaseHTTPRequestHandler):

      def do_HEAD(self) -> None:
        self.root_requested = (self.path == '/')
        resp_code = (200 if self.root_requested else 404)
        self.send_response(resp_code)
        if self.root_requested:
          self.send_header('Content-Type', 'text/html')
        self.end_headers()

      def do_GET(self) -> None:
        self.do_HEAD()
        if not self.root_requested: return
        for line in f_in:
          self.wfile.write(line)
          self.wfile.flush()
        self.server.shutdown()

    server = ThreadingHTTPServer(address, Handler)

    super().__init__(target=server.serve_forever)


if __name__ == '__main__': main()
