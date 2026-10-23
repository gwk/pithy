# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.web.app import WebApp
from pithy.web.auth import _access_attr, allow_public, requires_privileges
from pithy.web.request import Request
from pithy.web.response import Response
from utest import utest_exc, utest_run, utest_val


@utest_run
def _() -> None:
  'Simple app requirements are validated at class definition and snapshotted independently of decorator metadata.'
  class Restricted(WebApp):
    @requires_privileges('read')
    def handle_request(self, request:Request) -> Response:
      raise AssertionError('Resolution must not execute the handler.')

  app = Restricted()
  request = Request(method='GET', scheme='http', host='localhost', port=80, raw_path='/', query_str='', headers={},
    client_addr=('127.0.0.1', 0), content_length=None)
  setattr(Restricted.handle_request, _access_attr, frozenset())
  destination = app.resolve_destination(request)
  utest_val(frozenset({'read'}), destination.required_privileges)
  utest_val(True, destination.get_handler(request) is app)

  class Public(WebApp):
    @allow_public
    def handle_request(self, request:Request) -> Response: return Response()

  utest_val(frozenset(), Public().resolve_destination(request).required_privileges)

  def undeclared() -> None:
    class Undeclared(WebApp):
      def handle_request(self, request:Request) -> Response: return Response()

  def undeclared_override() -> None:
    class Override(Public):
      def handle_request(self, request:Request) -> Response: return Response()

  utest_exc(TypeError, undeclared)
  utest_exc(TypeError, undeclared_override)
  utest_exc(NotImplementedError, WebApp().resolve_destination, request) # The server responds 501.
