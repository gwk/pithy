# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from time import sleep
from typing import Any, cast, Iterable, Mapping, overload, Sequence

from starlette.authentication import requires
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.convertors import Convertor, register_url_convertor
from starlette.datastructures import FormData, QueryParams
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection, Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from ..csv import Quoting, render_csv
from ..date import Date, parse_time_12hmp, Time, TZInfo
from ..html import HtmlNode
from ..json import render_json
from ..markup import MuChildLax
from ..transtruct import bool_str_vals
from .endpoint import Endpoint
from .errors import ResponseError
from .request import Request as PithyRequest
from .requestconn import BodyTooLargeError, BytesConn
from .response import Response as PithyResponse
from .static import pithy_web_static_dir_path


_convenience_exports = (
  requires,
  RedirectResponse,
)


class ClientError(Exception):
  '''
  Indicates some kind of error in the client request.
  Use this in cases where the client error is caught and handled in application logic,
  as opposed to a true HTTPException with an error code.
  '''


class CsvResponse(Response):
  media_type = 'text/csv'

  def __init__(self, status_code:int=200, *, headers:Mapping[str,str]|None=None, background:BackgroundTask|None=None,
   quoting:Quoting|None=None, head:Sequence[str]|None, rows:Iterable[Sequence], **kwargs:Any) -> None:
    '''
    A CSV response.
    `head` is a tuple of column names.
    `rows` is an iterable of tuples of row values.
    '''

    super().__init__(content=render_csv(quoting=quoting, header=head, rows=rows), status_code=status_code, headers=headers,
      background=background, **kwargs)


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

  def __init__(self, *content:MuChildLax, status_code:int=200, headers:Mapping[str,str]|None=None,
   background:BackgroundTask|None=None, cache:bool=False, hx_push:str='', hx_refresh:bool=False, hx_redirect:str='',
   hx_location:str='', hx_trigger:str|Mapping[str,Any]='', hx_trigger_after_swap:str='', hx_trigger_after_settle:str='',
   fake_latency:float=0.0, **kwargs:Any) -> None:
    '''
    A response for one or more HTMX fragments.
    Fragments can be used to swap additional targets 'out-of-band' via the `hx-swap-oob` attribute.
    If `cache` is false the response will contain a `Cache-Control: no-store` header.
    `hx_trigger` sets the `HX-Trigger` header, which makes htmx dispatch client-side events after the response is handled.
    It is either a comma-separated string of event names, or a mapping of event names to `detail` objects, rendered as JSON.
    A `target` key in a detail is a selector for the element to dispatch on, instead of the requesting element.
    `hx_trigger_after_swap` and `hx_trigger_after_settle` are htmx 2 only; htmx 4 removed those headers.
    `FAKE_LATENCY` is a float in seconds used to simulate a slow response.
    '''

    headers = {**headers} if headers else {}
    if not cache: headers['Cache-Control'] = 'no-store'
    if hx_refresh: headers['HX-Refresh'] = 'true'
    if hx_push: headers['HX-Push'] = hx_push
    if hx_redirect: headers['HX-Redirect'] = hx_redirect
    if hx_location: headers['HX-Location'] = hx_location
    if hx_trigger: headers['HX-Trigger'] = render_json(hx_trigger, indent=None) if isinstance(hx_trigger, Mapping) else hx_trigger
    if hx_trigger_after_swap: headers['HX-Trigger-After-Swap'] = hx_trigger_after_swap
    if hx_trigger_after_settle: headers['HX-Trigger-After-Settle'] = hx_trigger_after_settle

    if fake_latency: sleep(fake_latency)

    content_str = '\n\n'.join(HtmlNode.render_child(c) for c in content)

    super().__init__(status_code=status_code, content=content_str, headers=headers, background=background, **kwargs)



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


def req_path_str(conn:HTTPConnection, key:str) -> str:
  '''
  Get a str value from a path parameter.
  If the key is not present or the value is not a string, raise a 400 exception.
  '''
  try: s = conn.path_params[key]
  except KeyError as e: raise HTTPException(400, f'Missing path parameter: {key}') from e
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


def req_path_nat(conn:HTTPConnection, key:str) -> int:
  '''
  Get a natural number (a non-negative integer) from a path parameter.
  If the key is not present or the value is not a natural number, raise a 400 exception.
  '''
  val = req_path_int(conn, key)
  if val < 0: raise HTTPException(400, f'Path parameter must be a natural number: {key}')
  return val


def req_path_pos_int(conn:HTTPConnection, key:str) -> int:
  '''
  Get a positive integer from a path parameter.
  If the key is not present or the value is not a positive integer, raise a 400 exception.
  '''
  val = req_path_int(conn, key)
  if val <= 0: raise HTTPException(400, f'Path parameter must be a positive integer: {key}')
  return val


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


def get_form_checkbox_bool(form_data:FormData, key:str) -> bool:
  '''
  Get a checkbox boolean value from a FormData (e.g. request.form).
  If the key is not present, return False.
  If the value is not a str (i.e. UploadFile) or does not equal the default "on" value,
  raise a 400 exception.
  '''
  v = get_form_str(form_data, key, default='')
  if v == '': return False
  if v == 'on': return True
  raise HTTPException(400, f'Invalid boolean form field value: {key}={v!r}')


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


def req_form_ints(form_data:FormData, key:str) -> list[int]:
  '''
  Get a required multi-valued int field from a FormData (e.g. request.form).
  If no values are present or any value is not convertible to an int, raise a 400 exception.
  '''
  els:list[int] = []
  for v in form_data.getlist(key):
    if not isinstance(v, str): raise HTTPException(400, f'Invalid form field type: {key}={v!r}')
    try: i = int(v)
    except ValueError as e: raise HTTPException(400, f'Invalid integer form field value: {key}={v!r}') from e
    els.append(i)
  if not els: raise HTTPException(400, f'Missing form field: {key!r}')
  return els


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

def get_query_str(query_params:QueryParams, key:str, default:str) -> str:
  '''
  Get a string value from a QueryParams (e.g. request.query_params).
  If the key is not present, return `default`.
  Note that this is merely a wrapper around QueryParams.get.
  It is provided for consistency with the other get_query_* functions so that we can more easily audit for usage of
  query_params.get as an indication of potentially unchecked query parameter access.
  '''
  return query_params.get(key, default)


def req_query_str(query_params:QueryParams, key:str) -> str:
  '''
  Get a string value from a QueryParams (e.g. request.query_params).
  If the key is not present, raise a 400 exception.
  '''
  v = query_params.get(key)
  if v is None: raise HTTPException(400, f'Missing query parameter: {key}')
  assert isinstance(v, str)
  return v


def get_query_bool(query_params:QueryParams, key:str, default:bool=False) -> bool:
  '''
  Get an optional boolean value from a QueryParams (e.g. request.query_params).
  If the key is not present or is the empty string, return `default`.
  If the value is not a str or does not equal one of the common boolean strings, raise a 400 exception.
  '''
  v = query_params.get(key, default='') # type: ignore[call-overload]
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
    if v == '': raise ValueError # Caught below.
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
  v = query_params.get(key, default='') # type: ignore[call-overload]
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
  v = query_params.get(key, default='') # type: ignore[call-overload]
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


def mount_for_static_pithy(*, path:str='/static/pithy', name:str='static_pithy') -> Mount:
  return Mount(path, app=StaticFiles(directory=pithy_web_static_dir_path(), follow_symlink=True), name=name)


def request_from_starlette(s_request:Request, conn:BytesConn) -> PithyRequest:
  '''
  Build a pithy Request from a Starlette request, using head information only.
  `conn` is the BytesConn that will serve the body once it has been read and set via `conn.set_body`.
  '''
  # Combine duplicate header lines into a single comma-separated value, matching the native server's `_headers_dict`.
  headers:dict[str,str] = {}
  for k, v in s_request.headers.items(): # Starlette lowercases keys and yields each raw header line separately.
    headers[k] = f'{headers[k]}, {v}' if k in headers else v

  cl_str = s_request.headers.get('content-length')
  content_length = int(cl_str) if cl_str is not None else None # A valid integer is guaranteed by uvicorn's HTTP parsing.

  client = s_request.client
  client_addr = (client.host, client.port) if client else ('', 0)

  url = s_request.url
  scheme = url.scheme

  # Application/integration state injected by Starlette middleware.
  # Read from the scope rather than the Starlette request .user or .session properties,
  # which raise AssertionError when their middleware is absent.
  # `session` is passed by reference so endpoint mutations propagate back to SessionMiddleware's cookie.
  ctx:dict[str,Any] = {}
  scope = s_request.scope
  if (user := scope.get('user')) is not None: ctx['user'] = user
  if (auth := scope.get('auth')) is not None: ctx['auth'] = auth
  if (session := scope.get('session')) is not None: ctx['session'] = session
  if cookies := s_request.cookies: ctx['cookies'] = cookies

  return PithyRequest(
    method=s_request.method,
    scheme=scheme,
    host=url.hostname or '',
    port=url.port or (443 if scheme == 'https' else 80),
    path=url.path,
    query_str=url.query,
    headers=headers,
    client_addr=client_addr,
    content_length=content_length,
    conn=conn,
    ctx=ctx,
  )


def convert_response(p_response:PithyResponse) -> Response:
  'Convert a pithy Response into a Starlette Response, preserving the exact status and headers.'
  body = p_response.body
  content = b'' if body is None else bytes(body)
  # Note: BufferedReader (file) bodies are not yet supported; pithy endpoints in rha return in-memory bodies.
  # When first needed, wrap the reader in a Starlette StreamingResponse.
  response = Response(content=content, status_code=p_response.status.value)
  response.raw_headers = p_response.headers_bytes_list() # Use pithy's exact wire headers (incl. content-length/type).
  return response


def _run_body(endpoint:Endpoint, request:PithyRequest) -> PithyResponse:
  '''
  Synchronous body phase, run in a threadpool: parse the body, fill body fields, and handle the request.
  Exceptions (ResponseError, BodyTooLargeError) propagate to the adapter's single catch site.
  '''
  endpoint.prepare(request)
  return endpoint.handle_request(request)


def endpoint_adapter(endpoint_cls:type[Endpoint], *, privileges:tuple[str,...]) -> Callable[[Request],Awaitable[Response]]:
  '''
  Adapt a pithy Endpoint subclass into an async callable suitable for a Starlette Route.
  `privileges` names the Starlette auth scopes the request must hold; an empty tuple declares the endpoint public.
  Declared privileges are enforced by applying Starlette's `requires` decorator, so a privileged adapter carries
  `__wrapped__` just like a decorated function endpoint, and a public adapter does not.
  '''

  # The parameter must be named `request`: `requires` inspects the signature for a parameter named
  # `request` or `websocket` and raises at decoration time otherwise.
  async def adapted(request:Request) -> Response:
    try:
      conn = BytesConn(b'')
      p_request = request_from_starlette(request, conn)
      endpoint = endpoint_cls(p_request, dict(request.path_params)) # Validates head params; may raise ResponseError.
      conn.set_body(await request.body()) # The body is only available here, in the async function.
      response = await run_in_threadpool(_run_body, endpoint, p_request)
    except ResponseError as e:
      response = PithyResponse.from_error(e, method=request.method)
    except BodyTooLargeError:
      response = PithyResponse(HTTPStatus.CONTENT_TOO_LARGE, body='Content Too Large', media_type='text/plain')
    return convert_response(response)

  # Wrap only when privileged: wrapping a public endpoint would give it a `__wrapped__` and break the invariant
  # that wrapped implies privileged.
  if privileges: return cast(Callable[[Request],Awaitable[Response]], requires(list(privileges))(adapted))
  return adapted


def endpoint_route(path:str, endpoint_cls:type[Endpoint], *, privileges:tuple[str,...]) -> Route:
  '''
  Build a Starlette Route that dispatches to a pithy Endpoint via the adapter, with methods taken from the Endpoint.
  `privileges` is passed through to the adapter; see `endpoint_adapter`.
  The Route is named for the Endpoint class so that each converted route has a distinct name rather than the
  adapter closure's name.
  '''
  # Resolve field converters now, so that an unconstructible field type raises early.
  endpoint_cls._resolve_converters()
  return Route(path, endpoint_adapter(endpoint_cls, privileges=privileges), methods=sorted(endpoint_cls._methods),
    name=endpoint_cls.__name__)
