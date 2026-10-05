# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ....html import A, H1, Li, Main, Ul
from ...request import Request
from ...response import HtmlResponse
from ..pages import dev_page


def dev_html_index(request:Request) -> HtmlResponse:
  'Index of developer HTML reference pages.'
  return dev_page(title='HTML', breadcrumbs=[('/', 'Home'), ('/html', 'HTML')],
    main=Main(H1('HTML'), Ul(
      Li(A(href='/html/controls', _='Form Controls'), ': Demonstrates form controls.'),
      Li(A(href='/html/nonportable', _='Nonportable Form Controls'), ': Month and week inputs.'))))
