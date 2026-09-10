# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Literal

from ...html import Button, Div, Form, H1, HtmlNode, Input, Label, Main, P, Pre, Script, Select
from ..endpoint import Endpoint, NoFields
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

  def handle_endpoint(self, request:Request, fields:NoFields) -> HtmlResponse:
    settings = Form(id='markdown-settings', hx_post='/markdown/settings.htmx',
      hx_trigger='change', hx_target='#markdown-editor', hx_swap='outerMorph', hx_sync='this:drop',
      hx_disable='#markdown-settings input, #markdown-settings select',
      hx_vals="js:{markdown: document.getElementById('markdown-editor').getValue()}",
      _=[
        Label(Input(type='checkbox', name='toolbar', value='true', checked=''), ' Show toolbar'),
        Label(Input(type='checkbox', name='show_stats', value='true'), ' Show statistics'),
        Label(Input(type='checkbox', name='auto_resize', value='true'), ' Auto-resize'),
        Label('Theme', attrs_by_ref={'for': 'markdown-theme'}),
        Select(id='markdown-theme', name='theme').options({'solar': 'Light', 'cave': 'Dark'}, value='solar'),
      ])
    # Lock both typing and toolbar actions until the settings response is applied, including error responses.
    settings['hx-on::before:request'] = "document.getElementById('markdown-editor').inert = true;"
    settings['hx-on::finally:request'] = "document.getElementById('markdown-editor').inert = false;"
    return dev_page(title='Markdown Editor', breadcrumbs=[('/', 'Home'), ('/markdown', 'Markdown Editor')],
      main=Main(H1('Markdown Editor'),
        P('Write Markdown, then try different settings. Use the editor toolbar to switch between editing and preview.'),
        Script(src='/static/pithy/overtype/overtype-webcomponent.min.js', defer=''),
        Div(cl='markdown-settings', _=[settings,
          Button('Show Markdown value', type='button', hx_post='/markdown/value.htmx', hx_target='#markdown-value',
            hx_swap='innerHTML', hx_vals="js:{markdown: document.getElementById('markdown-editor').getValue()}"),
        ]),
        Pre(id='markdown-value', aria_label='Markdown value', aria_live='polite'),
        markdown_editor(markdown=sample_markdown),
        P('Settings changes may reset undo history and selection. OverType 2.4.2 also has a known issue with literal '
          'backslash escape sequences when settings change.')))


class MarkdownSettingsHtmx(Endpoint):
  methods = 'POST'
  max_body_bytes = 1024 * 1024

  class Fields:
    toolbar:bool|None
    show_stats:bool|None
    auto_resize:bool|None
    theme:Theme
    markdown:str

  def handle_endpoint(self, request:Request, fields:Fields) -> HtmxResponse:
    editor = markdown_editor(markdown=fields.markdown, toolbar=bool(fields.toolbar), show_stats=bool(fields.show_stats),
      auto_resize=bool(fields.auto_resize), theme=fields.theme)
    editor['inert'] = '' # The request's finally handler unlocks the editor after the morph completes.
    return HtmxResponse(editor)


class MarkdownValueHtmx(Endpoint):
  methods = 'POST'
  max_body_bytes = 1024 * 1024

  class Fields:
    markdown:str

  def handle_endpoint(self, request:Request, fields:Fields) -> HtmxResponse:
    return HtmxResponse(fields.markdown)
