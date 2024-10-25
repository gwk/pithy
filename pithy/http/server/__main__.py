# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from asyncio import run as aio_run, start_server

from ...web.app import WebApp
from . import HttpServer


def main() -> None:
  parser = ArgumentParser()
  parser.add_argument('-port' , type=int, default=0)
  args = parser.parse_args()
  aio_run(run(port=args.port))


async def run(host='127.0.0.1', port=0) -> None:
  server = HttpServer(app=WebApp(), host=host, port=port, dbg=True)
  await server.create_aio_server()
  await server.serve_forever()


if __name__ == "__main__": main()
