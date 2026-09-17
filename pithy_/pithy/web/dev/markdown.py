# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Literal

from ...html import A, Button, Div, Form, H1, H2, HtmlNode, Input, Label, Li, Main, P, Pre, Section, Select, Ul
from ..endpoint import Endpoint
from ..request import Request
from ..response import HtmlResponse, HtmxResponse
from .pages import dev_page


type Theme = Literal['solar','cave']

sample_markdown = '''# Project notes

A **Markdown editor** for descriptions, notes, and instructions.

## Next steps

- Review the proposal
- Share [feedback](https://example.com)
- [ ] Schedule a meeting

```python
print("Hello, world!")
```
'''


def markdown_editor(*, markdown:str, toolbar:bool=True, show_stats:bool=False, auto_resize:bool=False,
 theme:Theme='solar') -> HtmlNode:
  el = HtmlNode(tag='overtype-editor', id='markdown-editor', theme=theme, height='auto' if auto_resize else '360px', min_height='180px',
    value=markdown, aria_label='Markdown editor')
  for name, enabled in (('toolbar', toolbar), ('show-stats', show_stats), ('auto-resize', auto_resize)):
    if enabled: el[name] = ''
  return el


class DevMarkdown(Endpoint):
  'Demonstrates OverType configured by external HTML controls through HTMX.'

  def get(self, request:Request, fields:None) -> HtmlResponse:
    settings = Form(id='markdown-settings', hx_post='/markdown/settings.htmx',
      hx_trigger='change', hx_target='#markdown-editor', hx_swap='outerMorph', hx_sync='this:drop',
      hx_disable='#markdown-settings input, #markdown-settings select',
      hx_vals="js:{markdown: document.getElementById('markdown-editor').getValue()}",
      _=[
        # Each setting is an independent bool, so each uses a bool checkbox, which always sends 'true' or 'false'.
        Label(Input.bool_checkbox(name='toolbar', is_checked=True), ' Show toolbar'),
        Label(Input.bool_checkbox(name='show_stats', is_checked=False), ' Show statistics'),
        Label(Input.bool_checkbox(name='auto_resize', is_checked=False), ' Auto-resize'),
        Label('Theme', for_='markdown-theme'),
        Select(id='markdown-theme', name='theme').options({'solar': 'Light', 'cave': 'Dark'}, value='solar'),
      ])
    # Lock both typing and toolbar actions until the settings response is applied, including error responses.
    settings['hx-on::before:request'] = "document.getElementById('markdown-editor').inert = true;"
    settings['hx-on::finally:request'] = "document.getElementById('markdown-editor').inert = false;"
    return dev_page(title='Markdown Editor', breadcrumbs=[('/', 'Home'), ('/markdown', 'Markdown Editor')],
      js_paths=['/static/pithy/overtype/overtype-webcomponent.min.js', '/static/dev/markdown.js'],
      main=Main(H1('Markdown Editor'),
        P('Write Markdown and see the preview update as you type. Try different settings with the controls below.'),
        Div(cl='markdown-settings', _=[settings,
          Button('Show Markdown source', type='button', popovertarget='markdown-source-popover',
            hx_post='/markdown/value.htmx', hx_target='#markdown-value',
            hx_swap='innerHTML', hx_vals="js:{markdown: document.getElementById('markdown-editor').getValue()}"),
        ]),
        Div(cl='markdown-layout', _=[
          Section(H2('Editor'), markdown_editor(markdown=sample_markdown)),
          Section(H2('Preview', id='markdown-preview-heading'),
            Div(id='markdown-preview', aria_labelledby='markdown-preview-heading')),
        ]),
        Div(id='markdown-source-popover', cl='panel flow', popover='', role='dialog',
          aria_labelledby='markdown-source-heading', _=[
            H2('Markdown source', id='markdown-source-heading'),
            P('The editor value posted through HTMX and returned by the server as plain text.'),
            Pre(id='markdown-value', aria_label='Markdown source', aria_live='polite'),
            Button('Close', type='button', popovertarget='markdown-source-popover', popovertargetaction='hide', autofocus=''),
          ]),
        Ul(cl='font-small', _=[
          Li('Settings changes may reset undo history and selection.'),
          Li('OverType 2.4.2 has a ', A('known issue', href='https://github.com/panphora/overtype/issues/123'),
            r': when settings rebuild the editor, it converts literal \n, \r, and \t sequences into newline, '
            'carriage return, and tab characters, which can alter the Markdown.'),
          Li('Preview checkboxes are read-only in this demo. They can be made interactive by updating the corresponding '
            'Markdown task markers when clicked.')])))


class MarkdownSettingsHtmx(Endpoint):
  max_body_bytes = 1024 * 1024

  class Post:
    toolbar:bool
    show_stats:bool
    auto_resize:bool
    theme:Theme
    markdown:str

  def post(self, request:Request, fields:Post) -> HtmxResponse:
    editor = markdown_editor(markdown=fields.markdown, toolbar=fields.toolbar, show_stats=fields.show_stats,
      auto_resize=fields.auto_resize, theme=fields.theme)
    editor['inert'] = '' # The request's finally handler unlocks the editor after the morph completes.
    return HtmxResponse(editor)


class MarkdownValueHtmx(Endpoint):
  max_body_bytes = 1024 * 1024

  class Post:
    markdown:str

  def post(self, request:Request, fields:Post) -> HtmxResponse:
    return HtmxResponse(fields.markdown)
