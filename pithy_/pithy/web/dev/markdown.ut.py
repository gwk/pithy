# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from base64 import b64decode
from hashlib import sha256
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
  return post_body(path, 'application/x-www-form-urlencoded', urlencode(fields).encode())


def post_multipart(path:str, *parts:tuple[bytes,bytes]) -> Response:
  'Post multipart form data; each part is a pair of header lines and content.'
  body = b''.join(b'--boundary\r\n' + headers + b'\r\n\r\n' + content + b'\r\n' for headers, content in parts)
  return post_body(path, 'multipart/form-data; boundary=boundary', body + b'--boundary--\r\n')


def post_body(path:str, content_type:str, body:bytes) -> Response:
  req = Request(method='POST', scheme='http', host='localhost', port=80, path=path, query_str='',
    headers={'content-type': content_type}, client_addr=('127.0.0.1', 0), content_length=len(body), conn=BytesConn(body))
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
  form = document.query_one('form#markdown-form')
  assert form is not None and form.attrs is not None
  utest_val(('post', 'multipart/form-data'), (form.attrs.get('method'), form.attrs.get('enctype')),
    desc='Attachments require a multipart post')
  textarea = document.query_one('form#markdown-form > markdown-editor#markdown-editor > textarea#markdown-text')
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
    utest_val('attachments', editor.attrs.get('attachments'), desc='The morph must keep the attachments field name')
    utest_val(True, 'hx-morph-skip-children' in editor.attrs, desc='The morph must keep the existing textarea')
    utest_val(0, len(response.query('textarea')), desc='Settings responses do not carry the text')
  utest_exc(BadRequestError, post, '/markdown/settings.htmx', {}) # Bool fields are required.
  utest_exc(BadRequestError, post, '/markdown/settings.htmx', {'auto_resize': 'true', 'markdown': ''})


def file_part(filename:str, content_type:str, data:bytes) -> tuple[bytes,bytes]:
  headers = f'Content-Disposition: form-data; name="attachments"; filename="{filename}"\r\nContent-Type: {content_type}'
  return (headers.encode(), data)


@utest_run
def _() -> None:
  'The rendering shows the text as received and embeds the exact bytes of each referenced image.'
  text_headers = b'Content-Disposition: form-data; name="markdown"'
  # Every byte value, with a sequence that resembles the multipart delimiter.
  png = bytes(range(256)) + b'\r\n--boundar\r\n\x00' + bytes(reversed(range(256)))
  jpg = b'\xff\xd8\xff second'
  markdown = ('# <Title> & more\r\n\r\nFirst ![Image 1](attachment:image-1.png) then ![Image 2](attachment:image-2.jpg).\r\n'
    '![Again](attachment:image-1.png) ![Missing](attachment:image-9.png) ![Vector](attachment:image-3.svg)\r\n')
  body = post_multipart('/markdown/render', (text_headers, markdown.encode()),
    file_part('image-1.png', 'image/png', png), file_part('image-2.jpg', 'image/jpeg', jpg),
    file_part('image-3.svg', 'image/svg+xml', b'<svg/>'), file_part('image-4.png', 'image/png', b'unreferenced')).body
  assert isinstance(body, bytes)
  document = JustHTML(body, sanitize=False)
  source = document.query_one('pre#markdown-source')
  assert source is not None
  utest_val(markdown.replace('\r\n', '\n'), source.to_text(separator='', strip=False), desc='The source is shown as received')
  srcs = [str((el.attrs or {}).get('src')) for el in source.query('img')]
  embedded = [(src.partition(',')[0], b64decode(src.partition(',')[2])) for src in srcs]
  utest_val([('data:image/png;base64', png), ('data:image/jpeg;base64', jpg), ('data:image/png;base64', png)], embedded,
    desc='Image data round trips; an unlisted type is not embedded')
  listing = document.query_one('ul#markdown-attachments')
  assert listing is not None
  items = [item.to_text() for item in listing.query('li')]
  utest_val(4, len(items))
  utest_val(True, sha256(png).hexdigest() in items[0] and f'{len(png)} bytes' in items[0])
  utest_val(True, 'type not embedded' in items[2])
  utest_val(True, 'not referenced' in items[3])
  missing = document.query_one('p#markdown-missing')
  assert missing is not None
  utest_val(True, 'image-9.png' in missing.to_text())

  body = post_multipart('/markdown/render', (text_headers, b'No images.')).body
  assert isinstance(body, bytes)
  document = JustHTML(body, sanitize=False)
  utest_val(0, len(document.query('img, ul#markdown-attachments, p#markdown-missing')))
  utest_exc(BadRequestError, post_multipart, '/markdown/render', file_part('image-1.png', 'image/png', png))
  utest_exc(BadRequestError, post_multipart, '/markdown/render', (text_headers, b''),
    (b'Content-Disposition: form-data; name="attachments"', b'not a file'))
