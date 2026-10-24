# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Drive `WebServer` connections over a scripted socket, without any network access.
'''

from socket import socket as Socket
from typing import cast

from pithy.web.app import WebApp
from pithy.web.server import ServerConfig, WebServer


class TestSocket:
  '''
  Feed raw HTTP through h11 without opening a network socket.

  Successive `recv` calls return the chunks in order, splitting any chunk larger than the requested size.
  Empty chunks are ignored. Once the chunks are exhausted, `recv` returns EOF.
  Send number `fail_send` (counting from 1) raises BrokenPipeError.
  '''

  def __init__(self, *chunks:bytes, fail_send:int=0) -> None:
    self.chunks = [chunk for chunk in chunks if chunk]
    self.fail_send = fail_send
    self.sends = 0

  def settimeout(self, timeout:float) -> None: pass
  def shutdown(self, how:int) -> None: pass
  def close(self) -> None: pass

  def recv(self, size:int) -> bytes:
    if not self.chunks: return b''
    chunk = self.chunks[0]
    if len(chunk) > size: self.chunks[0] = chunk[size:]
    else: del self.chunks[0]
    return chunk[:size]

  def sendall(self, data:bytes) -> None:
    self.sends += 1
    if self.sends == self.fail_send: raise BrokenPipeError('Client disconnected.')


def handle_connection(app:WebApp, socket:TestSocket, *, log_access:bool) -> None:
  'Handle one client connection from 127.0.0.1:4321 on a server that has no listening socket.'
  server = WebServer.__new__(WebServer)
  server.app = app
  server.config = ServerConfig(log_access=log_access)
  server._handle_connection(cast(Socket, socket), ('127.0.0.1', 4321))
