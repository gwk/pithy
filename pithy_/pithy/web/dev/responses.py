# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.
from ...html import Html, Main
from ..response import HtmlResponse


def page_html(*, title:str, main:Main) -> HtmlResponse:
  'Return an HTML page with `main` content.'
  html = Html().doc(title=title)
  head = html.head
  head.add_stylesheet(href='/pithy.css')
  head.add_js(src='https://cdn.jsdelivr.net/npm/htmx.org@4.0.0-beta1/dist/htmx.min.js')
  html.append(main)
  return HtmlResponse(body=html)
