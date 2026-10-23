# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .auth import Privileges
from .handler import RequestHandler
from .request import Request


_context_keywords_ = ['authorization', 'dispatch', 'handler construction']


@dataclass(frozen=True)
class Destination(ABC):
  '''
  A selected recipient and its access requirements, before handler acquisition.

  Resolution must not construct handlers or read request bodies. The server checks `required_privileges`
  before calling `get_handler`. Calling `get_handler` directly does not enforce access.
  '''
  required_privileges:Privileges


  @abstractmethod
  def get_handler(self, request:Request) -> RequestHandler:
    'Return or construct the handler after the server has authorized the request.'
    raise NotImplementedError
