# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ...html import Code, Form, H1, HtmlNode, Input, Label, Li, Main, P, TextArea, Ul
from ..endpoint import Endpoint
from ..request import Request
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


def markdown_editor(*, markdown:str|None, auto_resize:bool=False) -> HtmlNode:
  '''
  The `markdown-editor` element defined by `pithy/web/static/markdown.js`.
  It wraps an ordinary textarea, which holds the text and submits under the name `markdown`.
  If `markdown` is None then the textarea is omitted; this form is only suitable as a morph response.
  '''
  el = HtmlNode(tag='markdown-editor', id='markdown-editor')
  # A morph updates the element's attributes and leaves its children alone,
  # so the browser's textarea keeps its text, selection and undo history.
  el['hx-morph-skip-children'] = ''
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
    main=Main(H1('Markdown Editor'),
      P('A plain textarea with Markdown syntax coloring. The syntax stays visible, '
        'so the text can be copied to and from issues and agent conversations unchanged.'),
      settings,
      markdown_editor(markdown=sample_markdown),
      Ul(cl='font-small', _=[
        Li('The settings response morphs only the attributes of the editor element. '
          'The text, selection and undo history are not affected.'),
        Li('The editor is a form control: the textarea submits like any other, and no script is needed to read its value.'),
        Li('Coloring is computed per line. Fenced code blocks are tracked across lines; ',
          'emphasis and links that span a line break are not colored.'),
        Li('The script and stylesheet work under a strict Content Security Policy; see ',
          Code('pithy_/test/web/markdown-editor.html'), '.')])))


class MarkdownSettingsHtmx(Endpoint):
  max_body_bytes = 1024

  class Post:
    auto_resize:bool

  def post(self, request:Request, fields:Post) -> HtmxResponse:
    'Return the editor element without its textarea; the morph applies the attributes and keeps the existing children.'
    return HtmxResponse(markdown_editor(markdown=None, auto_resize=fields.auto_resize))
