# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import pithy

from ...web.reload import DevServerCmd
from ...web.server import ServerConfig, WebServer
from ._webtest import ChartTestApp


def main() -> None:
  DevServerCmd.parse_or_exit().serve(run, watch=[pithy])


def run(config:ServerConfig) -> None:
  WebServer(app=ChartTestApp(), config=config).serve_forever()


if __name__ == '__main__': main()
