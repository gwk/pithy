# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ....html import Code, H1, H2, Main, P, Section
from ....html.parts import hl_for_json
from ...request import Request
from ...response import HtmlResponse
from ..pages import dev_page


def dev_html_to_json(request:Request) -> HtmlResponse:
  'Examples of JSON rendered as nested HTML lists.'
  main = Main(
    H1('HTML to JSON'),
    P('JSON rendered as HTML lists by ', Code('hl_for_json'), '.'),
    Section(
      H2('Array of objects'),
      P('Eleven entries show the change from index 9 to 10. Each object has two keys to show continuation alignment.'),
      hl_for_json([{'email': f'person{idx}@example.com', 'name': f'Person {idx}'} for idx in range(11)])),
    Section(
      H2('Array of arrays'),
      P('Each inner array starts beside its outer index and restarts numbering at zero.'),
      hl_for_json([['red', 'green', 'blue'], ['cyan', 'magenta', 'yellow']])),
    Section(
      H2('Object of arrays'),
      P('Array values start on a new line beneath their object key.'),
      hl_for_json({'primary': ['red', 'green', 'blue'], 'secondary': ['cyan', 'magenta', 'yellow']})),
    Section(
      H2('Object of objects'),
      P('Nested objects use bullets at both levels.'),
      hl_for_json({'sender': {'email': 'alice@example.com', 'name': 'Alice'},
        'recipient': {'email': 'bob@example.com', 'name': 'Bob'}})),
  )
  return dev_page(title='HTML to JSON', main=main,
    breadcrumbs=[('/', 'Home'), ('/html', 'HTML'), ('/html/html-to-json', 'HTML to JSON')])
