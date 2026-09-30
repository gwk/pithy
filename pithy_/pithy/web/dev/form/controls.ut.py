# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus
from urllib.parse import urlencode, urlsplit

from pithy.web.dev.routes import routes
from pithy.web.request import Request
from pithy.web.requestconn import BytesConn
from pithy.web.response import Response
from pithy.web.router import Router
from utest import utest_run, utest_val


router = Router(routes)


def request(path:str, data:dict[str,str]|None=None, *, query:str='') -> Response:
  body = urlencode(data).encode() if data is not None else b''
  req = Request(method='POST' if data is not None else 'GET', scheme='http', host='localhost', port=80,
    path=path, query_str=query, headers={'content-type': 'application/x-www-form-urlencoded'} if data is not None else {},
    client_addr=('127.0.0.1', 0), content_length=len(body) if data is not None else None,
    conn=BytesConn(body) if data is not None else None)
  handler = router.resolve_handler(req)
  handler.prepare(req)
  return handler.handle_request(req)


@utest_run
def _() -> None:
  'Submitting the image shows its coordinates on a page where both forms still work.'
  image = request('/form/controls/image', {'x': '5', 'y': '8'})
  utest_val(HTTPStatus.SEE_OTHER, image.status)
  url = urlsplit(str(image.headers['location']))
  utest_val('/form/controls', url.path)
  utest_val('x=5&y=8', url.query)

  page = request(url.path, query=url.query)
  assert isinstance(page.body, bytes)
  html = page.body.decode()
  utest_val(2, html.count('<form'))
  utest_val(True, "method='post' action='/form/controls'" in html)
  utest_val(True, "method='post' action='/form/controls/image'" in html)
  utest_val(True, '<strong>x</strong>: 5' in html)
  utest_val(True, '<strong>y</strong>: 8' in html)

  again = request('/form/controls/image', {'x': '1', 'y': '2'})
  utest_val(HTTPStatus.SEE_OTHER, again.status)
  fields = {name: '' for name in ('text', 'email', 'number', 'password', 'tel', 'url', 'search', 'textarea',
    'date', 'time', 'datetime_local', 'color', 'range')}
  fields.update(hidden='hidden-value', checkbox='false', checkbox_set='\x00')
  main = request('/form/controls', fields)
  utest_val(HTTPStatus.OK, main.status)
