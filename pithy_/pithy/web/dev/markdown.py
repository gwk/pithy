# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from base64 import b64encode
from hashlib import sha256

from ...html import A, Code, Form, H1, H2, HtmlNode, Img, Input, Label, Li, Main, P, Pre, TextArea, Ul
from ..endpoint import Endpoint
from ..request import Request, UploadedFile
from ..response import HtmlResponse, HtmxResponse
from .pages import dev_page


sample_markdown = r"""# Heading

A lightweight **Markdown syntax editor**.

## Subheading

- Bullet point
- A [link](https://example.com) or https://example.com/docs
- [ ] A checkbox

> Quoted text, with `inline code` and ~~struck~~ words.

<example name="greeting">
Tags are colored, which helps when drafting prompts.
</example>

```python
print("Hello, world!")
```
"""


# The form field name for pasted images; see `MarkdownRender.Post`.
attachments_field = 'attachments'

# An image reference to an attachment, as inserted by markdown.js when an image is pasted.
attachment_ref_re = re.compile(r'!\[[^\]\n]*\]\(attachment:([\w.-]+)\)')

# Uploads of these types are embedded in the rendering. The type is claimed by the client, so it is checked against this list.
# SVG is omitted because it is a document format.
embeddable_types = frozenset({'image/gif', 'image/jpeg', 'image/png', 'image/webp'})


def markdown_editor(*, markdown:str|None, auto_resize:bool=False) -> HtmlNode:
  '''
  The `markdown-editor` element defined by `pithy/web/static/markdown.js`.
  It wraps an ordinary textarea, which holds the text and submits under the name `markdown`.
  If `markdown` is None then the textarea is omitted; this form is only suitable as a morph response.
  Pasted images are submitted as files under the name `attachments`; the enclosing form must be multipart.
  '''
  el = HtmlNode(tag='markdown-editor', id='markdown-editor')
  # A morph updates the element's attributes and leaves its children alone,
  # so the browser's textarea keeps its text, selection and undo history.
  el['hx-morph-skip-children'] = ''
  el['attachments'] = attachments_field
  if auto_resize: el['auto-resize'] = ''
  if markdown is not None:
    el.append(TextArea(markdown, id='markdown-text', name='markdown', aria_label='Markdown editor', spellcheck='false'))
  return el


def dev_markdown(request:Request) -> HtmlResponse:
  'Demonstrates the Markdown editor, configured by an external HTML control through HTMX.'
  settings = Form(id='markdown-settings', hx_post='/markdown/settings.htmx',
    hx_trigger='change', hx_target='#markdown-editor', hx_swap='outerMorph', hx_sync='this:drop',
    hx_disable='#markdown-settings input',
    _=[
      # A bool checkbox always sends 'true' or 'false'.
      Label(Input.bool_checkbox(name='auto_resize', is_checked=False), ' Auto-resize'),
    ])
  return dev_page(title='Markdown Editor', breadcrumbs=[('/', 'Home'), ('/markdown', 'Markdown Editor')],
    css_paths=['/static/pithy/markdown.css'], js_paths=['/static/pithy/markdown.js'],
    main=Main(cl='markdown-page', _=[H1('Markdown Editor'),
      P('A plain textarea with Markdown syntax coloring. The syntax stays visible, '
        'so the text can be copied to and from issues and agent conversations unchanged.'),
      settings,
      Form(id='markdown-form', cl='flow', method='post', action='/markdown/render', enctype='multipart/form-data', _=[
        markdown_editor(markdown=sample_markdown),
        Input(type='submit', value='Submit')]),
      Ul(cl='font-small', _=[
        Li('Paste an image to attach it. The editor inserts a reference such as ',
          Code('![Image 1](attachment:image-1.png)'), ' and lists the image below the text. ',
          'Deleting the reference detaches the image; undo attaches it again.'),
        Li('Submit posts the text and the referenced images as multipart form data. ',
          'The response shows the text as received, with each image embedded after its reference.'),
        Li('The settings response morphs only the attributes of the editor element. '
          'The text, selection and undo history are not affected.'),
        Li('The editor is a form control: the textarea submits like any other, and no script is needed to read its value.'),
        Li('Coloring is computed per line. Fenced code blocks are tracked across lines; ',
          'emphasis and links that span a line break are not colored.'),
        Li('The script and stylesheet work under a strict Content Security Policy; see ',
          Code('pithy_/test/web/markdown-editor.html'), '.')])]))


class MarkdownSettingsHtmx(Endpoint):
  max_body_bytes = 1024

  class Post:
    auto_resize:bool

  def post(self, request:Request, fields:Post) -> HtmxResponse:
    'Return the editor element without its textarea; the morph applies the attributes and keeps the existing children.'
    return HtmxResponse(markdown_editor(markdown=None, auto_resize=fields.auto_resize))



class MarkdownRender(Endpoint):
  'Receives the editor text and its attached images, and shows them as received.'
  max_body_bytes = 32 * 1024 * 1024

  class Post:
    markdown:str
    attachments:list[UploadedFile]|None # Absent when no image is attached.

  def post(self, request:Request, fields:Post) -> HtmlResponse:
    markdown = fields.markdown.replace('\r\n', '\n') # Form submission encodes textarea line breaks as CRLF.
    return dev_page(title='Markdown Rendering',
      breadcrumbs=[('/', 'Home'), ('/markdown', 'Markdown Editor'), ('/markdown/render', 'Rendering')],
      main=render_submission(markdown, fields.attachments or []))


def render_submission(markdown:str, attachments:list[UploadedFile]) -> Main:
  '''
  The rendering of a submission: the Markdown source as received, with each attached image embedded after its reference.
  The Markdown is not parsed beyond locating the attachment references.
  '''
  files = {f.filename: f for f in attachments}
  source = Pre(id='markdown-source')
  missing:list[str] = []
  referenced:set[str] = set()
  pos = 0
  for m in attachment_ref_re.finditer(markdown):
    name = m[1]
    file = files.get(name)
    if file is None:
      missing.append(name)
      continue
    referenced.add(name)
    if file.content_type not in embeddable_types: continue
    source.append(markdown[pos:m.end()])
    source.append(Img(src=f'data:{file.content_type};base64,{b64encode(file.data).decode()}', alt=name))
    pos = m.end()
  source.append(markdown[pos:])

  main = Main(cl='markdown-rendering', _=[H1('Markdown Rendering'), source, H2('Attachments')])
  if attachments:
    main.append(Ul(id='markdown-attachments', _=[
      Li(Code(f.filename), f': {f.content_type}, {len(f.data)} bytes, SHA-256 ', Code(sha256(f.data).hexdigest()),
        '' if f.filename in referenced else ' (not referenced)',
        '' if f.content_type in embeddable_types else ' (type not embedded)')
      for f in attachments]))
  else:
    main.append(P('No attachments were received.'))
  if missing:
    main.append(P(id='markdown-missing', _=['References without an attachment: ', ', '.join(missing), '.']))
  main.append(P(A(href='/markdown', _='Back to the editor')))
  return main
