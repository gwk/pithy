# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Run a uvicorn server that notifies systemd of readiness.
'''

from socket import socket
from sys import exit

from uvicorn import Config, Server
from uvicorn.supervisors import ChangeReload

from ..systemd import sd_notify_ready


class ReadyNotifyingServer(Server):
  '''
  A uvicorn Server that notifies systemd once it is listening.
  Under a Type=notify unit, `systemctl start` blocks until this point and fails if the process exits first.
  This class must live in an importable module, not a `__main__`: the reloader pickles `server.run` for a spawned child,
  and multiprocessing does not populate `__main__` from a package's `__main__.py`.
  '''

  async def startup(self, sockets:list[socket]|None=None) -> None:
    await super().startup(sockets=sockets)
    if self.started: sd_notify_ready()


def run_server(config:Config) -> None:
  '''
  Run a ReadyNotifyingServer for `config`, with the reloader if `config.reload` is set.
  This replicates the relevant parts of `uvicorn.run`, which does not allow a custom Server class.
  Exits with an error if the server fails to start.
  '''
  server = ReadyNotifyingServer(config)
  try:
    if config.should_reload: # The reloader supervises a worker process that runs the server.
      ChangeReload(config, target=server.run, sockets=[config.bind_socket()]).run()
    else:
      server.run()
      if not server.started: exit('Server failed to start.')
  except KeyboardInterrupt: pass
