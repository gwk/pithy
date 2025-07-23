# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus
from time import sleep
from typing import Any, Iterable, Mapping, overload, Sequence

from starlette.background import BackgroundTask
from starlette.convertors import Convertor, register_url_convertor
from starlette.datastructures import FormData, QueryParams
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection, Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from ..csv import Quoting, render_csv
from ..date import Date, parse_time_12hmp, Time, TZInfo
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
    quoting:Quoting|None=None,
    head:Sequence[str]|None,
    rows:Iterable[Sequence],
    **kwargs:Any) -> None:

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


class HtmlResponse(HTMLResponse):

    def __init__(self,
      content:HtmlNode,
      *,
      status_code:int=200,
      headers:Mapping[str,str]|None=None,
      background:BackgroundTask|None=None,
      **kwargs:Any) -> None:

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
    cache:bool=False,
    hx_push:str='',
    hx_refresh:bool=False,
    hx_redirect:str='',
    hx_location:str='',
    hx_trigger:str='',
    hx_trigger_after_swap:str='',
    hx_trigger_after_settle:str='',
    FAKE_LATENCY:float=0.0,
    **kwargs:Any) -> None:

    '''
    A response for one or more HTMX fragments.
    Fragments can be used to swap additional targets 'out-of-band' via the `hx-swap-oob` attribute.
    If `cache` is false the response will contain a `Cache-Control: no-store` header.
    `FAKE_LATENCY` is a float in seconds used to simulate a slow response.
    '''

    if any((cache, hx_push, hx_redirect, hx_location, hx_refresh, hx_trigger, hx_trigger_after_swap, hx_trigger_after_settle)):
      headers = {**headers} if headers else {}
      if not cache: headers['Cache-Control'] = 'no-store'
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
  def  register(cls, name:str='date') -> None:
    register_url_convertor(name, cls())


# Path parameter access.

def get_path_str(conn:HTTPConnection, key:str) -> str:
  '''
  Get a str value from a path parameter, or return the empty string.
  If the returned value is not a string then raise a TypeError.
  '''
  try: s = conn.path_params[key]
  except KeyError: return ''
  if not isinstance(s, str): raise TypeError(s)
  return s


@overload
def get_path_int(conn:HTTPConnection, key:str, default:int) -> int: ...

@overload
def get_path_int(conn:HTTPConnection, key:str, default:int|None=None) -> int|None: ...

def get_path_int(conn:HTTPConnection, key:str, default:int|None=None) -> int|None:
  '''
  Get an int value from a path parameter.
  If the key is not present or the value is the empty string, return the default value.
  Otherwise if the value is not convertible to an integer, raise a 400 exception.
  '''
  try: s = conn.path_params[key]
  except KeyError: return default
  if s == '': return default
  try: return int(s)
  except ValueError as e: raise HTTPException(400, f'Path parameter must be an integer: {key}') from e


def req_path_int(conn:HTTPConnection, key:str) -> int:
  '''
  Get an int value from a path parameter.
  If the key is not present or the value is not an int, raise a 400 exception.
  '''
  try: return int(conn.path_params[key])
  except KeyError as e: raise HTTPException(400, f'Missing path parameter: {key}') from e
  except ValueError as e: raise HTTPException(400, f'Path parameter must be an integer: {key}') from e


# Form parameter access.

def form_dict(form_data:FormData, valid_keys:Iterable[str]=()) -> dict[str,str]:
  '''
  Convert a FormData (e.g. request.form) to a dict, raising a 400 exception if any value is not a str.
  If `valid_keys` is provided, raise a 400 exception if any key in the FormData is not in `valid_keys`.
  '''
  d = {}
  valid_keys = frozenset(valid_keys)
  for k, v in form_data.items():
    if not isinstance(v, str): raise HTTPException(400, f'Invalid form field type: {k!r}={v!r}')
    if valid_keys and k not in valid_keys: raise HTTPException(400, f'Invalid form field: {k!r}')
    d[k] = v
  return d


@overload
def get_form_str(form_data:FormData, key:str, default:str) -> str: ...

@overload
def get_form_str(form_data:FormData, key:str, default:None=None) -> str|None: ...

def get_form_str(form_data:FormData, key:str, default:str|None=None) -> str|None:
  '''
  Get an optional string value from a FormData (e.g. request.form).
  If the key is not present, return `default` (None if not specified).
  If the value is not a str (i.e. UploadFile), raise a 400 exception.
  '''
  try: v = form_data[key]
  except KeyError: return default
  if not isinstance(v, str): raise HTTPException(400, f'Invalid form field type: {key}={v!r}')
  return v


def req_form_str(form_data:FormData, key:str) -> str:
  '''
  Get a required string value from a FormData (e.g. request.form).
  If the key is not present or the value is not a str (i.e. UploadFile), raise a 400 exception.
  '''
  try: v = form_data[key]
  except KeyError as e: raise HTTPException(400, f'Missing form field: {key!r}') from e
  if not isinstance(v, str): raise HTTPException(400, f'Invalid form field type: {key}={v!r}')
  return v


@overload
def get_form_bool(form_data:FormData, key:str, default:bool) -> bool: ...

@overload
def get_form_bool(form_data:FormData, key:str, default:None=None) -> bool|None: ...

def get_form_bool(form_data:FormData, key:str, default:bool|None=None) -> bool|None:
  '''
  Get an optional boolean value from a FormData (e.g. request.form).
  If the key is not present or is the empty string, return `default` (None if not specified).
  If the value is not a str (i.e. UploadFile) or does not equal one of the common boolean strings,
  raise a 400 exception.
  '''
  v = get_form_str(form_data, key, default='')
  if v == '': return default
  try: return bool_str_vals[v]
  except KeyError as e: raise HTTPException(400, f'Invalid boolean form field value: {key}={v!r}') from e


def req_form_bool(form_data:FormData, key:str) -> bool:
  '''
  Get a required boolean value from a FormData (e.g. request.form).
  If the key is not present, if the value is not a str (i.e. UploadFile),
  if the value is the empty string or does not equal one of the common boolean strings,
  raise a 400 exception.
  '''
  v = req_form_str(form_data, key)
  try:
    if v == '': raise ValueError
    return bool_str_vals[v]
  except (KeyError, ValueError) as e: raise HTTPException(400, f'Invalid boolean form field value: {key}={v!r}') from e


@overload
def get_form_int(form_data:FormData, key:str, default:int) -> int: ...

@overload
def get_form_int(form_data:FormData, key:str, default:None=None) -> int|None: ...

def get_form_int(form_data:FormData, key:str, default:int|None=None) -> int|None:
  '''
  Get an optional int value from a FormData (e.g. request.form).
  If the key is not present or the value is the empty string, return `default` (None if not specified).
  If the value is not convertible to an int, raise a 400 exception.
  '''
  v = get_form_str(form_data, key, default='')
  if v == '': return default
  try: return int(v)
  except ValueError as e: raise HTTPException(400, f'Invalid integer form field value: {key}={v!r}') from e


def req_form_int(form_data:FormData, key:str) -> int:
  '''
  Get a required int value from a FormData (e.g. request.form).
  If the key is not present or the value is not convertible to an int, raise a 400 exception.
  '''
  v = req_form_str(form_data, key)
  try: return int(v)
  except ValueError as e: raise HTTPException(400, f'Invalid integer form field value: {key}={v!r}') from e


def get_form_date(form_data:FormData, key:str, default:Date|None=None) -> Date|None:
  '''
  Get an optional date value from a FormData (e.g. request.form).
  If the key is not present or the value is the empty string, return `default`.
  Otheriwise if the value is not an isoformat date, raise a 400 exception.
  '''
  v = get_form_str(form_data, key, default='')
  if v == '': return default
  try: return Date.fromisoformat(v)
  except ValueError as e: raise HTTPException(400, f'Invalid date form field value: {key}={v!r}') from e



def req_form_date(form_data:FormData, key:str) -> Date:
  '''
  Get an optional date value from a FormData (e.g. request.form).
  If the key is not present or the value is not a valid date, raise a 400 exception.
  '''
  v = req_form_str(form_data, key)
  try: return Date.fromisoformat(v)
  except ValueError as e: raise HTTPException(400, f'Invalid date form field value: {key}={v!r}') from e



def req_form_time_12hmp(form_data:FormData, key:str, tz:TZInfo|None=None) -> Time:
  '''
  Get a required time value from a FormData (e.g. request.form).
  If the key is not present or the value is not a valid time, raise a 400 exception.
  This function requires input to be in the 12-hour (with AM/PM) time format.
  '''
  v = req_form_str(form_data, key)
  try: return parse_time_12hmp(v, tz=tz)
  except ValueError as e: raise HTTPException(400, f'Invalid time form field value: {key}={v!r}') from e


# Query parameter access.

def req_query_str(query_params:QueryParams, key:str) -> str:
  '''
  Get a string value from a QueryParams (e.g. request.query_params).
  If the key is not present, raise a 400 exception.
  '''
  v = query_params.get(key)
  if v is None: raise HTTPException(400, f'Missing query parameter: {key}')
  assert isinstance(v, str)
  return v


@overload
def get_query_bool(query_params:QueryParams, key:str, default:bool) -> bool: ...

@overload
def get_query_bool(query_params:QueryParams, key:str, default:None=None) -> bool|None: ...

def get_query_bool(query_params:QueryParams, key:str, default:bool|None=None) -> bool|None:
  '''
  Get an optional boolean value from a QueryParams (e.g. request.query_params).
  If the key is not present or is the empty string, return `default`.
  If the value is not a str or does not equal one of the common boolean strings, raise a 400 exception.
  '''
  v = query_params.get(key, default='')
  if v == '': return default
  try: return bool_str_vals[v]
  except KeyError as e: raise HTTPException(400, f'Invalid boolean query parameter: {key}={v!r}') from e


def req_query_bool(query_params:QueryParams, key:str) -> bool:
  '''
  Get a required boolean value from a QueryParams (e.g. request.query_params).
  If the key is not present or does not equal one of the common boolean strings, raise a 400 exception.
  '''
  v = req_query_str(query_params, key)
  try:
    if v == '': raise ValueError
    return bool_str_vals[v]
  except (KeyError, ValueError) as e: raise HTTPException(400, f'Invalid boolean query parameter: {key}={v!r}') from e


@overload
def get_query_int(query_params:QueryParams, key:str, default:int) -> int: ...

@overload
def get_query_int(query_params:QueryParams, key:str, default:None=None) -> int|None: ...

def get_query_int(query_params:QueryParams, key:str, default:int|None=None) -> int|None:
  '''
  Get an optional int value from a QueryParams (e.g. request.query_params).
  If the key is not present or is the empty string return `default`.
  If the value is not an int, raise a 400 exception.
  '''
  v = query_params.get(key, default='')
  if v == '': return default
  try: return int(v)
  except ValueError as e: raise HTTPException(400, f'Invalid integer query parameter: {key}={v!r}') from e


def req_query_int(query_params:QueryParams, key:str) -> int:
  '''
  Get an int value from a QueryParams (e.g. request.query_params).
  If the key is not present or the value is not an int, raise a 400 exception.
  '''
  v = req_query_str(query_params, key)
  try: return int(v)
  except ValueError as e: raise HTTPException(400, f'Invalid integer query parameter: {key}={v!r}') from e


@overload
def get_query_date(query_params:QueryParams, key:str, default:Date) -> Date: ...

@overload
def get_query_date(query_params:QueryParams, key:str, default:None=None) -> Date|None: ...

def get_query_date(query_params:QueryParams, key:str, default:Date|None=None) -> Date|None:
  '''
  Get an optional date value from a QueryParams (e.g. request.query_params).
  If the key is not present, return today's date according to the given timezone `tz`.
  If the value is not a valid date, raise a 400 exception.
  '''
  v = query_params.get(key, default='')
  if v == '': return default
  try: return Date.fromisoformat(v)
  except ValueError as e: raise HTTPException(400, f'Invalid date query parameter: {key}={v!r}') from e


def req_query_date(query_params:QueryParams, key:str) -> Date:
  '''
  Get a required date value from a QueryParams (e.g. request.query_params).
  If the key is not present or the value is not a valid date, raise a 400 exception.
  '''
  v = req_query_str(query_params, key)
  try: return Date.fromisoformat(v)
  except ValueError as e: raise HTTPException(400, f'Invalid date query parameter: {key}={v!r}') from e


# Miscellaneous.

def empty_favicon(request:Request) -> Response:
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


def mount_for_static_pithy(*, path:str='/static/pithy', name:str='static_pithy') -> Mount:
  from . import static
  module_dir = real_path(static.__path__[0])
  assert is_dir(module_dir, follow=False), module_dir
  return Mount(path, app=StaticFiles(directory=module_dir, follow_symlink=True), name=name)
