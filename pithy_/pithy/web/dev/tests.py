# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Browser regression checks, run on demand in the dev app.'

from ...html import Button, Code, H1, Main, Ol, P
from ..request import Request
from ..response import HtmlResponse
from .pages import dev_page


def dev_tests(request:Request) -> HtmlResponse:
  return dev_page(title='Tests', main=Main(
    H1('Browser tests'),
    P('These checks run automatically in your current browser. They exercise color inheritance and themed components '
      'using the live stylesheets. Run this page in Chromium and WebKit after shared style changes.'),
    P('Fixtures run in a separate frame so they can change themes without changing this page. '
      'These checks cover browser behavior, not visual quality or accessibility.'),
    Button('Run again', id='tests-run', type='button'),
    P('Waiting for JavaScript.', id='tests-summary', role='status', aria_live='polite'),
    Ol(id='tests-results', cl='flow'),
    P('Automation can await ', Code('window.pithyDevTests'), ' for the current run. '
      'It resolves to ', Code('{status, results}'), ' with named results and failure messages.'),
  ), breadcrumbs=[('/', 'Home'), ('/tests', 'Tests')],
    css_paths=['/static/dev/tests.css'], js_paths=['/static/dev/tests.js'])
