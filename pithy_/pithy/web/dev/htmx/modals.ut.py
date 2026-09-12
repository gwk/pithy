# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import replace
from json import loads
from typing import Any
from urllib.parse import urlencode

from pithy.web.dev.domain_events import DomainEvent
from pithy.web.dev.htmx.modals import privileges_text, ui_text, users, vip_text
from pithy.web.dev.routes import routes
from pithy.web.errors import BadRequestError, NotFoundError
from pithy.web.request import Request
from pithy.web.requestconn import BytesConn
from pithy.web.response import Response
from pithy.web.router import Router
from utest import utest_exc, utest_run, utest_val


router = Router(routes)


type FormData = dict[str,str|list[str]]


def request(path:str, data:FormData|None=None) -> Response:
  body = urlencode(data, doseq=True).encode() if data is not None else b''
  req = Request(method='POST' if data is not None else 'GET', scheme='http', host='localhost', port=80,
    path=path, query_str='', headers={'content-type': 'application/x-www-form-urlencoded'} if data is not None else {},
    client_addr=('127.0.0.1', 0), content_length=len(body), conn=BytesConn(body))
  handler = router.resolve_handler(req)
  handler.prepare(req)
  return handler.handle_request(req)


def request_text(path:str) -> str:
  body = request(path).body
  assert isinstance(body, bytes)
  return body.decode()


@utest_run
def _() -> None:
  'The shared editor updates both views and emits a body event without a swap fragment.'
  original = users.copy()
  try:
    page = request_text('/htmx/modals')
    edit_url = '/htmx/modals/users/1/edit_modal.htmx'
    utest_val(2, page.count(edit_url), desc='Both contexts open the same editor')
    utest_val(2, page.count(f'{DomainEvent.user_updated} from:body'), desc='Both views listen for updates')
    modal = request_text(edit_url)
    utest_val(True, "dialog class='modal'" in modal, desc='Uses the standard dismissible modal')
    utest_val(True, "value='Alex Morgan'" in modal, desc='Editor contains current name')
    utest_val(True, "type='checkbox' name='vip'" in modal, desc='VIP checkbox is unchecked')
    utest_val(True, "name='privileges' value='publish' checked=''" in modal, desc='Held privilege is checked')
    utest_val(True, "name='privileges' value='moderate' data-pithy-checkbox='set'" in modal,
      desc='Unheld privilege is unchecked')
    utest_val(True, "value='auto' checked" in modal, desc='UI radio reflects current state')
    expected = original[1]
    updates:tuple[tuple[FormData,dict[str,Any]],...] = (
      ({'name': 'Alex Chen'}, {'name': 'Alex Chen'}),
      ({'role': 'Viewer'}, {'role': 'Viewer'}),
      ({'vip': 'true'}, {'vip': True}),
      ({'vip': 'false'}, {'vip': False}),
      ({'vip': 'true'}, {'vip': True}),
      ({'privileges': ['billing', 'moderate']}, {'privileges': frozenset({'moderate', 'billing'})}),
      ({'privileges': '\x00'}, {'privileges': frozenset()}), # The pithy.js empty-set marker.
      ({'privileges': 'billing'}, {'privileges': frozenset({'billing'})}),
      ({'ui': 'dark'}, {'ui': 'dark'}))
    for data, changes in updates:
      expected = replace(expected, **changes)
      response = request('/htmx/modals/users/1/update.htmx', data)
      utest_val({DomainEvent.user_updated: {'target': 'body'}}, loads(str(response.headers['hx-trigger'])))
      utest_val(b'', response.body, desc='Update endpoint has no view-specific fragment')
      utest_val(expected, users[1], desc=f'{data} is saved')
      # Check the complete rendered row and detail lines, so that a stale field or another user's row cannot satisfy the check.
      row = (f"<td class='nowrap'>{expected.name}</td>\n<td class='nowrap'>{expected.role}</td>\n"
        f"<td class='nowrap'>{vip_text(expected)}</td>\n<td>{privileges_text(expected)}</td>\n"
        f"<td class='nowrap'>{ui_text(expected.ui)}</td>")
      utest_val(True, row in request_text('/htmx/modals/users.htmx'), desc=f'Users table reflects {data}')
      detail = request_text('/htmx/modals/user_detail.htmx')
      for line in (f'Name: {expected.name}', f'Role: {expected.role}', f'VIP: {vip_text(expected)}',
        f'Privileges: {privileges_text(expected)}', f'UI: {ui_text(expected.ui)}'):
        utest_val(True, f'<p>{line}</p>' in detail, desc=f'User detail reflects {data}')
    modal = request_text(edit_url)
    utest_val(True, "type='checkbox' checked='' name='vip'" in modal, desc='VIP checkbox reflects saved state')
    utest_val(True, "name='privileges' value='billing' checked=''" in modal, desc='Privileges reflect saved state')
    utest_val(True, "name='privileges' value='publish' data-pithy-checkbox='set'" in modal)
    utest_val(True, "value='dark' checked" in modal, desc='UI radio reflects saved state')
    utest_val('Sam Rivera', users[2].name, desc='Other users are unchanged')
    utest_val('Editor', users[2].role)
    utest_val(False, users[2].vip)
    utest_val(frozenset(), users[2].privileges)
    utest_val('light', users[2].ui)
    saved = users.copy()
    invalids:tuple[FormData,...] = ({'name': ' '}, {'role': 'Owner'}, {'vip': 'maybe'}, {'privileges': 'root'},
      {'privileges': ['publish', '\x00']}, {'ui': 'sepia'}, {}, {'name': 'Alex', 'role': 'Viewer'},
      {'vip': 'false', 'ui': 'light'}, {'privileges': '\x00', 'vip': 'true'})
    for invalid in invalids:
      utest_exc(BadRequestError, request, '/htmx/modals/users/1/update.htmx', invalid)
      utest_val(saved, users, desc='Invalid updates leave data unchanged')
    utest_exc(NotFoundError, request, '/htmx/modals/users/999/edit_modal.htmx')
    utest_exc(NotFoundError, request, '/htmx/modals/users/999/update.htmx', {'name': 'Nobody'})
  finally:
    users.clear()
    users.update(original)
