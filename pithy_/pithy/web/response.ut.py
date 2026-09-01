# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus

from pithy.html import Div, Span
from pithy.web.response import CsvResponse, HtmxResponse, RedirectResponse
from utest import utest_exc, utest_run, utest_val


@utest_run
def test_csv_response() -> None:
  r = CsvResponse(head=['a', 'b'], rows=[(1, 2), ('x,y', 3)])
  utest_val(b'a,b\r\n1,2\r\n"x,y",3\r\n', r.body, desc='CsvResponse body')
  utest_val('text/csv;charset=utf-8', r.headers['content-type'], desc='CsvResponse content-type')
  utest_val(19, r.headers['content-length'], desc='CsvResponse content-length')

  headless = CsvResponse(head=None, rows=[(1,)])
  utest_val(b'1\r\n', headless.body, desc='CsvResponse headless body')


@utest_run
def test_htmx_response() -> None:
  r = HtmxResponse(Div('a'), Span('b'), 'c<d')
  utest_val(b'<div>a</div>\n\n\n<span>b</span>\n\n\nc&lt;d', r.body, desc='HtmxResponse body')
  utest_val('text/html;charset=utf-8', r.headers['content-type'], desc='HtmxResponse content-type')
  utest_val('no-store', r.headers['cache-control'], desc='HtmxResponse cache-control')

  cached = HtmxResponse(Div('a'), cache=True)
  utest_val(None, cached.headers.get('cache-control'), desc='HtmxResponse cached cache-control')

  hx = HtmxResponse(hx_push='/p', hx_refresh=True, hx_redirect='/r', hx_location='/l', hx_trigger='t')
  utest_val('/p', hx.headers['hx-push-url'], desc='HtmxResponse hx-push-url')
  utest_val('true', hx.headers['hx-refresh'], desc='HtmxResponse hx-refresh')
  utest_val('/r', hx.headers['hx-redirect'], desc='HtmxResponse hx-redirect')
  utest_val('/l', hx.headers['hx-location'], desc='HtmxResponse hx-location')
  utest_val('t', hx.headers['hx-trigger'], desc='HtmxResponse hx-trigger')

  hx_json = HtmxResponse(hx_trigger={'itemsChanged': {'id': 1}})
  utest_val('{"itemsChanged":{"id":1}}', hx_json.headers['hx-trigger'], desc='HtmxResponse hx-trigger json')


@utest_run
def test_redirect_response() -> None:
  r = RedirectResponse('/next page?a=1')
  utest_val(HTTPStatus.TEMPORARY_REDIRECT, r.status, desc='RedirectResponse status')
  utest_val('/next%20page?a=1', r.headers['location'], desc='RedirectResponse location')
  utest_val(None, r.body, desc='RedirectResponse body')
  utest_val(0, r.headers['content-length'], desc='RedirectResponse content-length')

  other = RedirectResponse('/other', status=HTTPStatus.SEE_OTHER)
  utest_val(HTTPStatus.SEE_OTHER, other.status, desc='RedirectResponse explicit status')


utest_exc(ValueError, RedirectResponse, '/x', status=HTTPStatus.OK)
utest_exc(ValueError, RedirectResponse, '/x', headers={'location':'/y'})
