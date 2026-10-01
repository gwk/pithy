# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from urllib.parse import urlencode

from justhtml import JustHTML
from pithy.web.dev.markdown import markdown_editor
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
  'The page renders the editor around a textarea; settings responses carry attributes only.'
  req = Request(method='GET', scheme='http', host='localhost', port=80, path='/markdown', query_str='',
    headers={}, client_addr=('127.0.0.1', 0), content_length=None)
  page = router.resolve_handler(req).handle_request(req).body
  assert isinstance(page, bytes)
  document = JustHTML(page, sanitize=False)
  utest_val(1, len(document.query('form#markdown-settings')))
  textarea = document.query_one('markdown-editor#markdown-editor > textarea#markdown-text')
  assert textarea is not None and textarea.attrs is not None
  utest_val('markdown', textarea.attrs.get('name'), desc='The textarea submits as an ordinary form control')
  markdown = r'literal \n or \t <script> &amp;'
  rendered = JustHTML(''.join(markdown_editor(markdown=markdown).render()), sanitize=False)
  rendered_textarea = rendered.query_one('markdown-editor > textarea#markdown-text')
  assert rendered_textarea is not None
  utest_val(markdown, rendered_textarea.to_text(strip=False), desc='The editor preserves textarea content')
  srcs = [src for el in document.query('script') if (src := (el.attrs or {}).get('src'))]
  utest_val(True, '/static/pithy/markdown.js' in srcs)
  hrefs = [(el.attrs or {}).get('href') for el in document.query('link')]
  utest_val(True, '/static/pithy/markdown.css' in hrefs)
  # The page's markdown demo must not depend on inline event handlers or evaluated expressions.
  for el in document.query('main *'):
    for name, value in (el.attrs or {}).items():
      utest_val(False, name.startswith('hx-on') or name == 'style', desc=f'No inline handler or style: {name}')
      utest_val(False, str(value).startswith(('js:', 'javascript:')), desc=f'No evaluated attribute value: {name}')
  for enabled in (False, True):
    flag = str(enabled).lower() # Bool checkboxes always send 'true' or 'false'; see `Input.bool_checkbox`.
    body = post('/markdown/settings.htmx', {'auto_resize': flag}).body
    assert isinstance(body, bytes)
    response = JustHTML(body, sanitize=False)
    editor = response.query_one('markdown-editor#markdown-editor')
    assert editor is not None and editor.attrs is not None
    utest_val(enabled, 'auto-resize' in editor.attrs)
    utest_val(True, 'hx-morph-skip-children' in editor.attrs, desc='The morph must keep the existing textarea')
    utest_val(0, len(response.query('textarea')), desc='Settings responses do not carry the text')
  utest_exc(BadRequestError, post, '/markdown/settings.htmx', {}) # Bool fields are required.
  utest_exc(BadRequestError, post, '/markdown/settings.htmx', {'auto_resize': 'true', 'markdown': ''})
