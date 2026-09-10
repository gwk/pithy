# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from urllib.parse import urlencode

from lxml.html import fromstring
from pithy.web.dev.routes import routes
from pithy.web.errors import BadRequestError
from pithy.web.request import Request
from pithy.web.requestconn import BytesConn
from pithy.web.response import Response
from pithy.web.router import Router
from utest import utest_exc, utest_run, utest_val


router = Router(routes)


def post(path:str, fields:dict[str,str]) -> Response:
  body = urlencode(fields).encode()
  req = Request(method='POST', scheme='http', host='localhost', port=80, path=path, query_str='',
    headers={'content-type': 'application/x-www-form-urlencoded'}, client_addr=('127.0.0.1', 0),
    content_length=len(body), conn=BytesConn(body))
  handler = router.resolve_handler(req)
  handler.prepare(req)
  return handler.handle_request(req)


@utest_run
def _() -> None:
  'Settings responses return the submitted Markdown with the requested configuration.'
  req = Request(method='GET', scheme='http', host='localhost', port=80, path='/markdown', query_str='',
    headers={}, client_addr=('127.0.0.1', 0), content_length=None)
  page = router.resolve_handler(req).handle_request(req).body
  assert isinstance(page, bytes)
  document = fromstring(page)
  utest_val(1, len(document.xpath('//form[@id="markdown-settings"]')))
  utest_val(1, len(document.xpath('//pre[@id="markdown-value"]/following-sibling::overtype-editor')))
  for markdown in ('', '## My edits\n<script>"hello"</script> & \\n'):
    for enabled in (False, True):
      settings = {'theme': 'cave', 'markdown': markdown}
      if enabled: settings.update(toolbar='true', show_stats='true', auto_resize='true')
      body = post('/markdown/settings.htmx', settings).body
      assert isinstance(body, bytes)
      el = fromstring(body)
      utest_val('cave', el.get('theme'))
      for attr in ('toolbar', 'show-stats', 'auto-resize'):
        utest_val(enabled, attr in el.attrib)
      utest_val(markdown, el.get('value'), desc='Python returns the exact submitted Markdown')
      utest_val(True, 'inert' in el.attrib, desc='Editor stays locked until the request finishes')
  utest_exc(BadRequestError, post, '/markdown/settings.htmx', {'theme': 'unknown', 'markdown': ''})
  utest_exc(BadRequestError, post, '/markdown/settings.htmx', {'theme': 'solar'})
  response = post('/markdown/value.htmx', {'markdown': '<script>alert(1)</script>\n**hello**'})
  utest_val(b'&lt;script>alert(1)&lt;/script>\n**hello**', response.body, desc='Markdown is displayed as escaped text')
  utest_val(b'', post('/markdown/value.htmx', {'markdown': ''}).body)
