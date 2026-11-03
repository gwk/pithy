# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.web.dev.routes import routes
from pithy.web.request import Request
from pithy.web.router import Router
from utest import utest_run, utest_val


router = Router(routes, default_public=True)


def request_text(path:str, query_str:str='') -> str:
  req = Request(method='GET', scheme='http', host='localhost', port=80, raw_path=path, query_str=query_str, headers={},
    client_addr=('127.0.0.1', 0), content_length=None)
  handler = router.resolve_route(req).get_handler(req)
  handler.prepare_for_request(req)
  body = handler.handle_request(req).body
  assert isinstance(body, bytes)
  return body.decode()


@utest_run
def _() -> None:
  'The modals page renders a reusable dialog for each closedby value, and the transient dialog only on request.'
  page = request_text('/html/modals')
  for closedby in ('any', 'closerequest', 'none'):
    utest_val(True, f"data-open-modal='modal-closedby-{closedby}'" in page, desc=f'Opener for closedby={closedby}')
    utest_val(True, f"id='modal-closedby-{closedby}' class='modal' closedby='{closedby}'" in page,
      desc=f'Reusable dialog with closedby={closedby}')
  utest_val(False, 'data-transient-modal' in page, desc='No transient dialog by default')
  utest_val(False, '<script>' in page, desc='No inline script')

  page = request_text('/html/modals', 'on_load=true')
  dialog = "<dialog class='modal' data-transient-modal='' closedby='none' aria-labelledby='transient-modal-title'>"
  utest_val(True, dialog in page, desc='Transient dialog requires acknowledgement')
  utest_val(False, '<script>' in page, desc='No inline script with the transient dialog')
