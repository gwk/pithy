# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Browser regression checks, run on demand in the dev app.'

from ...html import A, Button, Code, H1, Li, Main, Ol, P, Ul
from ..request import Request
from ..response import HtmlResponse
from .pages import dev_page


fixture_pages = (
  ('/static/dev/tests/content-setup.html', 'Content setup',
    'Checks that pithy.js configures the initial document and swapped-in content: '
    'collapsible tables across repeated morphs, table head setup after outerHTML and out-of-band swaps, '
    'and modal display, dismissal and removal.'),
  ('/static/dev/tests/checkbox-inclusion.html', 'Checkbox inclusion',
    'Checks boolean and set checkbox submission through hx-include and prefixed attributes, '
    'including inheritance, append behavior, disabled controls and explicit value overrides. '
    'Requests are canceled before transmission.'),
  ('/static/dev/tests/markdown-editor.html', 'Markdown editor',
    'Checks the markdown-editor element under a strict Content Security Policy: syntax coloring, exact text round trips, '
    'equal layout of the textarea and its coloring layer, survival of DOM replacement, and pasted image attachments.'),
)
'''
Self-contained regression pages, each as (path, name, description).
Each page loads `static/tests/suite.js` and reports its outcome through it.
'''


def dev_tests(request:Request) -> HtmlResponse:
  return dev_page(title='Tests', main=Main(
    H1('Browser tests'),
    P('These checks run automatically in your current browser. '
      'Run this page in Chromium and WebKit after changing the pithy.web static scripts or stylesheets.'),
    P('The style checks exercise document layout, flow, color inheritance and themed components using the live stylesheets. '
      'Their fixtures run in a separate frame so they can change themes without changing this page. '
      'These checks cover browser behavior, not visual quality or accessibility.'),
    P('Each fixture page below then runs in its own frame, because its checks need a fresh document. '
      'A fixture page can also be opened directly; it shows its own result.'),
    Ul(id='tests-suites', _=[Li(A(href=path, _=name), ': ', desc) for path, name, desc in fixture_pages]),
    Button('Run again', id='tests-run', type='button'),
    P('Waiting for JavaScript.', id='tests-summary', role='status', aria_live='polite'),
    Ol(id='tests-results', cl='flow'),
    P('Automation can await ', Code('window.pithyDevTests'), ' for the current run. '
      'It resolves to ', Code('{status, results}'), ' with named results and failure messages.'),
  ), breadcrumbs=[('/', 'Home'), ('/tests', 'Tests')],
    css_paths=['/static/dev/tests.css'], js_paths=['/static/dev/tests.js'])
