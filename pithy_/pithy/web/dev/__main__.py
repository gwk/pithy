# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import pithy

from ..reload import DevServerCmd
from ..router import RouterApp
from ..server import ServerConfig, WebServer
from ..static import pithy_web_static_dir_path
from .pages import DevStaticFiles
from .routes import routes


_context_keywords_ = ['demo application', 'development server', 'hot reload', 'http', 'web framework']


'''
DevApp is a web app for devolpers to explore the web framework.
For integration tests, see `pithy.web.testapp`.
'''


def main() -> None:
  'Parent process (watcher) entrypoint.'
  # Static assets are read on each request, so editing them needs no restart.
  DevServerCmd.parse_or_exit().serve(run, watch=[pithy], ignore=[pithy_web_static_dir_path(), DevStaticFiles.local_dir])


def run(config:ServerConfig) -> None:
  'The child process (reloaded) entrypoint.'
  app = DevApp()
  server = WebServer(app=app, config=config)
  server.serve_forever()


class DevApp(RouterApp):

  def __init__(self) -> None:
    super().__init__(routes=routes, default_public=True)



if __name__ == '__main__': main()
