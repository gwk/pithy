# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus
from time import sleep
from typing import Iterable, Sequence

from pithy.csv import render_csv
from starlette.convertors import Convertor, register_url_convertor
from starlette.datastructures import FormData
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection, Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from ..date import Date
from ..html import HtmlNode
from ..markup import MuChildLax
from ..transtruct import bool_str_vals
from ..url import fmt_url


class CsvResponse(Response):
    media_type = 'text/csv'


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


def req_query_int(request:Request, key:str) -> int:
  '''
  Get an int value from a request's query string.
  If the key is not present or the value is not an int, raise 400.
  '''
  v = request.query_params.get(key)
  if v is None: raise HTTPException(400, f'missing query parameter: {key}')
  try: return int(v)
  except ValueError: raise HTTPException(400, f'invalid query parameter: {key}={v!r}')


def req_query_str(request:Request, key:str) -> str:
  '''
  Get a string value from a request's query string.
  If the key is not present, raise 400.
  '''
  v = request.query_params.get(key)
  if v is None: raise HTTPException(400, f'missing query parameter: {key}')
  return v


def get_form_str(form_data:FormData, key:str, default:str|None=None) -> str|None:
  '''
  Get a string value from a request's FormData.
  If the key is not present or the value is not a str (i.e. UploadFile), return `default` (None if not specified).
  '''
  v = form_data.get(key)
  return v if isinstance(v, str) else default


def get_form_bool(form_data:FormData, key:str) -> bool|None:
  '''
  Get a boolean value from a request's FormData.
  If the key is not present, is not a str (i.e. UploadFile), or does not equal one of the common boolean strings, return None.
  '''
  v = form_data.get(key)
  if not isinstance(v, str): return None
  return bool_str_vals.get(v)


def csv_response(*, quoting:int|None=None, header:Sequence[str]|None, rows:Iterable[Sequence]) -> CsvResponse:
  '''
  Return a CSV response.
  `head` is a tuple of column names.
  `rows` is an iterable of tuples of row values.
  '''
  return CsvResponse(content=render_csv(quoting=quoting, header=header, rows=rows))


def htmx_response(*content:MuChildLax, FAKE_LATENCY=0.0) -> HTMLResponse:
  '''
  Return a response for one or more HTMX fragments.
  The first fragment is swapped into the target element.
  Subsequent fragments can be used to swap other targets 'out-of-band' via the `hx-swap-oob` attribute.
  `FAKE_LATENCY` is a float in seconds to simulate a slow response.
  '''
  if FAKE_LATENCY: sleep(FAKE_LATENCY)
  return HTMLResponse(content='\n\n'.join(HtmlNode.render_child(c) for c in content))


def empty_favicon(HTMLRequest) -> Response:
  '''
  Return an empty favicon; this should be used as a fallback route for '/favicon.ico'.
  Using this prevents 404s getting logged for favicon requests.
  '''
  return HTMLResponse(content=b'', media_type='image/x-icon')


def redirect_to_signin_response(conn:HTTPConnection, exc:Exception|None=None) -> RedirectResponse:
  '''
  Return a response that redirects to the signin page, encoding the current URL as the `next` query parameter.
  The usage of `next` matches that of Starlette's `requires` decorator when `redirect` is specified.
  The exception argument is ignored; it exists to make this function compatible with Starlette.exception_handlers,
  and is intended for 403 Forbidden exceptions.
  '''
  signin_url = fmt_url('/signin', next=conn.url.path)
  return RedirectResponse(url=signin_url, status_code=HTTPStatus.SEE_OTHER)
