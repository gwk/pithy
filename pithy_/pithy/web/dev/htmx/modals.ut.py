# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from json import loads
from urllib.parse import urlencode

from pithy.web.dev.domain_events import DomainEvent
from pithy.web.dev.htmx.modals import users
from pithy.web.dev.routes import routes
from pithy.web.errors import BadRequestError, NotFoundError
from pithy.web.request import Request
from pithy.web.requestconn import BytesConn
from pithy.web.response import Response
from pithy.web.router import Router
from utest import utest_exc, utest_run, utest_val


router = Router(routes)


def request(path:str, data:dict[str,str]|None=None) -> Response:
  body = urlencode(data).encode() if data is not None else b''
  req = Request(method='POST' if data is not None else 'GET', scheme='http', host='localhost', port=80,
    path=path, query_str='', headers={'content-type': 'application/x-www-form-urlencoded'} if data is not None else {},
    client_addr=('127.0.0.1', 0), content_length=len(body), conn=BytesConn(body))
  handler = router.resolve_handler(req)
  handler.prepare(req)
  return handler.handle_request(req)


@utest_run
def _() -> None:
  'The shared editor updates both views and emits a body event without a swap fragment.'
  original = users.copy()
  try:
    page = str(request('/htmx/modals').body)
    edit_url = '/htmx/modals/users/1/edit_modal.htmx'
    utest_val(2, page.count(edit_url), desc='Both contexts open the same editor')
    utest_val(2, page.count(f'{DomainEvent.user_updated} from:body'), desc='Both views listen for updates')
    modal = str(request(edit_url).body)
    utest_val(True, "dialog class='modal'" in modal, desc='Uses the standard dismissible modal')
    utest_val(True, "value='Alex Morgan'" in modal, desc='Editor contains current name')
    for data, expected in (({'name': 'Alex Chen'}, 'Alex Chen'), ({'role': 'Viewer'}, 'Viewer')):
      response = request('/htmx/modals/users/1/update.htmx', data)
      utest_val({DomainEvent.user_updated: {'target': 'body'}}, loads(str(response.headers['hx-trigger'])))
      utest_val(b'', response.body, desc='Update endpoint has no view-specific fragment')
      for path in ('/htmx/modals/users.htmx', '/htmx/modals/user_detail.htmx'):
        utest_val(True, expected in str(request(path).body), desc=f'{path} reflects saved change')
    utest_val('Sam Rivera', users[2].name, desc='Other users are unchanged')
    utest_val('Editor', users[2].role)
    saved = users.copy()
    for invalid in ({'name': ' '}, {'role': 'Owner'}, {}, {'name': 'Alex', 'role': 'Viewer'}):
      utest_exc(BadRequestError, request, '/htmx/modals/users/1/update.htmx', invalid)
      utest_val(saved, users, desc='Invalid updates leave data unchanged')
    utest_exc(NotFoundError, request, '/htmx/modals/users/999/edit_modal.htmx')
    utest_exc(NotFoundError, request, '/htmx/modals/users/999/update.htmx', {'name': 'Nobody'})
  finally:
    users.clear()
    users.update(original)
