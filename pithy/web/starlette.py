# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from time import sleep

from starlette.convertors import Convertor, register_url_convertor
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from ..date import Date
from ..html import HtmlNode
from ..markup import MuChildLax


class DateConverter(Convertor):
  '''
  A simple converter to get ISO dates out out of URL paths in a Starlette Router.
  To register with Starlette: `DateConverter.register()`.
  To use in a route: `Route('/calendar/{date:date}', calendar_endpoint)`
  '''

  regex = '[0-9]{4}-[0-9]{2}-[0-9]{2}'

  def convert(self, value:str) -> Date:
    try: return Date.fromisoformat(value)
    except ValueError as e: raise HTTPException(404) from e


  def to_string(self, value:Date) -> str: return value.isoformat()


  @classmethod
  def  register(cls, name='date') -> None:
    register_url_convertor(name, cls())


def htmx_response(*content:MuChildLax, FAKE_LATENCY=0.0) -> HTMLResponse:
  '''
  Return a response for one or more HTMX fragments.
  The first fragment is swapped into the target element.
  Subsequent fragments can be used to swap other targets 'out-of-band' via the `hx-swap-oob` attribute.
  `FAKE_LATENCY` is a float in seconds to simulate a slow response.
  '''
  if FAKE_LATENCY: sleep(FAKE_LATENCY)
  return HTMLResponse(content='\n\n'.join(HtmlNode.render_child(c) for c in content))
