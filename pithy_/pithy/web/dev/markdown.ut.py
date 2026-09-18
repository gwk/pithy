# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import environ
from unittest.mock import patch
from urllib.parse import urlencode

from justhtml import JustHTML
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
  document = JustHTML(page, sanitize=False)
  utest_val(1, len(document.query('form#markdown-settings')))
  utest_val(1, len(document.query('div[popover] pre#markdown-value')))
  for debug, suffix in (('0', '.min'), ('1', '')):
    with patch.dict(environ, WEB_DBG=debug):
      body = router.resolve_handler(req).handle_request(req).body
    assert isinstance(body, bytes)
    scripts = [src for el in JustHTML(body, sanitize=False).query('script') if (src := (el.attrs or {}).get('src'))]
    for stem in ('htmx/htmx4', 'overtype/overtype-webcomponent'):
      utest_val([f'/static/pithy/{stem}{suffix}.js'], [src for src in scripts if src.startswith(f'/static/pithy/{stem}')])
  for markdown in ('', '## My edits\n<script>"hello"</script> & \\n'):
    for enabled in (False, True):
      flag = str(enabled).lower() # Bool checkboxes always send 'true' or 'false'; see `Input.bool_checkbox`.
      settings = {'theme': 'cave', 'markdown': markdown, 'toolbar': flag, 'show_stats': flag, 'auto_resize': flag}
      body = post('/markdown/settings.htmx', settings).body
      assert isinstance(body, bytes)
      el = JustHTML(body, sanitize=False).query_one('overtype-editor')
      assert el is not None and el.attrs is not None
      utest_val('cave', el.attrs.get('theme'))
      for attr in ('toolbar', 'show-stats', 'auto-resize'):
        utest_val(enabled, attr in el.attrs)
      utest_val(markdown, el.attrs.get('value'), desc='Python returns the exact submitted Markdown')
      utest_val(True, 'inert' in el.attrs, desc='Editor stays locked until the request finishes')
  all_false = {'toolbar': 'false', 'show_stats': 'false', 'auto_resize': 'false'}
  utest_exc(BadRequestError, post, '/markdown/settings.htmx', {'theme': 'unknown', 'markdown': '', **all_false})
  utest_exc(BadRequestError, post, '/markdown/settings.htmx', {'theme': 'solar', **all_false})
  utest_exc(BadRequestError, post, '/markdown/settings.htmx', {'theme': 'solar', 'markdown': ''}) # Bool fields are required.
  response = post('/markdown/value.htmx', {'markdown': '<script>alert(1)</script>\n**hello**'})
  utest_val(b'&lt;script>alert(1)&lt;/script>\n**hello**', response.body, desc='Markdown is displayed as escaped text')
  utest_val(b'', post('/markdown/value.htmx', {'markdown': ''}).body)
