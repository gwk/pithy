# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus
from time import sleep
from typing import Iterable, Mapping, Sequence

from starlette.background import BackgroundTask
from starlette.convertors import Convertor, register_url_convertor
from starlette.datastructures import FormData
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection, Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from ..csv import render_csv
from ..date import Date
from ..fs import is_dir, real_path
from ..html import HtmlNode
from ..markup import MuChildLax
from ..transtruct import bool_str_vals
from ..url import fmt_url


class ClientError(Exception):
  '''
  Indicates some kind of error in the client request.
  Use this in cases where the client error is caught and handled in application logic,
  as opposed to a true HTTPException with an error code.
  '''


class CsvResponse(Response):
  media_type = 'text/csv'

  def __init__(self,
    status_code:int=200,
    *,
    headers:Mapping[str,str]|None=None,
    background:BackgroundTask|None=None,
    quoting:int|None=None,
    head:Sequence[str]|None,
    rows:Iterable[Sequence],
    **kwargs) -> None:

    '''
    A CSV response.
    `head` is a tuple of column names.
    `rows` is an iterable of tuples of row values.
    '''

    super().__init__(
      content=render_csv(quoting=quoting, header=head, rows=rows),
      status_code=status_code,
      headers=headers,
      background=background,
      **kwargs)


def csv_response(*args, **kwargs) -> CsvResponse: return CsvResponse(*args, **kwargs)


class HtmlResponse(HTMLResponse):

    def __init__(self,
      content:HtmlNode,
      *,
      status_code:int=200,
      headers:Mapping[str,str]|None=None,
      background:BackgroundTask|None=None,
      **kwargs) -> None:

      '''
      An HTML response.
      '''

      super().__init__(
        status_code=status_code,
        content=content.render_str(),
        headers=headers,
        background=background,
        **kwargs)


class HtmxResponse(HTMLResponse):

  def __init__(self,
    *content:MuChildLax,
    status_code:int=200,
    headers:Mapping[str,str]|None=None,
    background:BackgroundTask|None=None,
    hx_push:str='',
    hx_refresh:bool=False,
    hx_redirect:str='',
    hx_location:str='',
    hx_trigger:str='',
    hx_trigger_after_swap:str='',
    hx_trigger_after_settle:str='',
    FAKE_LATENCY=0.0,
    **kwargs) -> None:

    '''
    A response for one or more HTMX fragments.
    Fragments can be used to swap other targets 'out-of-band' via the `hx-swap-oob` attribute.
    `FAKE_LATENCY` is a float in seconds used to simulate a slow response.
    '''

    if any((hx_push, hx_redirect, hx_location, hx_refresh, hx_trigger, hx_trigger_after_swap, hx_trigger_after_settle)):
      headers = {**headers} if headers else {}
      if hx_refresh: headers['HX-Refresh'] = 'true'
      if hx_push: headers['HX-Push'] = hx_push
      if hx_redirect: headers['HX-Redirect'] = hx_redirect
      if hx_location: headers['HX-Location'] = hx_location
      if hx_trigger: headers['HX-Trigger'] = hx_trigger
      if hx_trigger_after_swap: headers['HX-Trigger-After-Swap'] = hx_trigger_after_swap
      if hx_trigger_after_settle: headers['HX-Trigger-After-Settle'] = hx_trigger_after_settle

    if FAKE_LATENCY: sleep(FAKE_LATENCY)

    super().__init__(
      status_code=status_code,
      content='\n\n'.join(HtmlNode.render_child(c) for c in content),
      headers=headers,
      background=background,
      **kwargs)


def htmx_response(*content:MuChildLax, background:BackgroundTask|None=None, FAKE_LATENCY=0.0) -> HtmxResponse:
  return HtmxResponse(*content, background=background, FAKE_LATENCY=FAKE_LATENCY)



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


def req_query_bool(request:Request, key:str) -> bool:
  '''
  Get a boolean value from a request's query string.
  If the key is not present or does not equal one of the common boolean strings, raise a 400 exception.
  '''
  v = request.query_params.get(key)
  if v is None: raise HTTPException(400, f'missing query parameter: {key}')
  try: return bool_str_vals[v]
  except KeyError: raise HTTPException(400, f'invalid boolean query parameter: {key}={v!r}')


def req_query_int(request:Request, key:str) -> int:
  '''
  Get an int value from a request's query string.
  If the key is not present or the value is not an int, raise a 400 exception.
  '''
  v = request.query_params.get(key)
  if v is None: raise HTTPException(400, f'missing query parameter: {key}')
  try: return int(v)
  except ValueError: raise HTTPException(400, f'invalid integer query parameter: {key}={v!r}')


def req_query_str(request:Request, key:str) -> str:
  '''
  Get a string value from a request's query string.
  If the key is not present, raise a 400 exception.
  '''
  v = request.query_params.get(key)
  if v is None: raise HTTPException(400, f'missing query parameter: {key}')
  assert isinstance(v, str)
  return v


def get_form_bool(form_data:FormData, key:str, default:bool|None=None) -> bool|None:
  '''
  Get a boolean value from a request's FormData.
  If the key is not present, is not a str (i.e. UploadFile), or does not equal one of the common boolean strings,
  return `default` (None if not specified).
  '''
  v = form_data.get(key)
  if not isinstance(v, str): return default
  return bool_str_vals.get(v, default)


def get_form_int(form_data:FormData, key:str, default:int|None=None) -> int|None:
  '''
  Get an int value from a request's FormData.
  If the key is not present or the value is not an int, return `default` (None if not specified).
  '''
  v = form_data.get(key)
  if not isinstance(v, str) or v == '': return default
  try: return int(v)
  except ValueError: return default


def get_form_str(form_data:FormData, key:str, default:str|None=None) -> str|None:
  '''
  Get a string value from a request's FormData.
  If the key is not present or the value is not a str (i.e. UploadFile), return `default` (None if not specified).
  '''
  v = form_data.get(key)
  return v if isinstance(v, str) else default


def req_form_bool(form_data:FormData, key:str) -> bool:
  '''
  Get a boolean value from a request's FormData.
  If the key is not present, is not a str (i.e. UploadFile), or does not equal one of the common boolean strings,
  raise a 400 exception.
  '''
  v = form_data.get(key)
  if not isinstance(v, str): raise HTTPException(400, f'missing form field: {key}')
  try: return bool_str_vals[v]
  except KeyError: raise HTTPException(400, f'invalid boolean form field: {key}={v!r}')


def req_form_int(form_data:FormData, key:str) -> int:
  '''
  Get an int value from a request's FormData.
  If the key is not present or the value is not an int, raise a 400 exception.
  '''
  v = form_data.get(key)
  if not isinstance(v, str): raise HTTPException(400, f'missing form field: {key}')
  try: return int(v)
  except ValueError: raise HTTPException(400, f'invalid integer form field: {key}={v!r}')


def req_form_str(form_data:FormData, key:str) -> str:
  '''
  Get a string value from a request's FormData.
  If the key is not present or the value is not a str (i.e. UploadFile), raise a 400 exception.
  '''
  v = form_data.get(key)
  if not isinstance(v, str): raise HTTPException(400, f'missing form field: {key}')
  return v


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


def mount_for_static_pithy(*, path:str='/static/pithy', name='static_pithy') -> Mount:
  from . import static
  module_dir = real_path(static.__path__[0])
  assert is_dir(module_dir, follow=False), module_dir
  return Mount(path, app=StaticFiles(directory=module_dir, follow_symlink=True), name=name)
