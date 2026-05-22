# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Mapping
from datetime import date, datetime, time
from http import HTTPStatus
from inspect import get_annotations
from typing import Any, ClassVar, get_origin, get_type_hints

from ..transtruct import PrefigureFn, TranstructFn, Transtructor, TranstructorError
from .errors import BadRequestError
from .handler import RequestHandler
from .request import Request, UploadedFile
from .response import Response


class Endpoint(RequestHandler):
  '''
  Base class for request endpoints. An Endpoint instance is created for each request.

  Subclasses declare typed fields that are automatically populated from request parameters (path, query, body).
  The field types determine how raw values are converted.

  Use `T|None` to mark a field as optional (None if the parameter is absent).
  Use `list[T]` to collect multiple values for one key (e.g. multi-select).
  Use `list[T]|None` for an optional multi-value field (None if no values are submitted).

  To add custom type conversions, define `_prefigures` as a class variable mapping types to prefigure functions:
    class MyEndpoint(Endpoint):
      _prefigures = {MyType: lambda cls, val, ctx: MyType.from_string(val)}
      my_field: MyType

  All Endpoint classes take the following constructor parameters:
  * `request:Request`
  * `path_params:dict[str,object]`

  Request handling flow:
  * The server constructs the endpoint, which fills fields from path and query params.
    Duplicates across path and query, excess params not corresponding to fields, and conversion failures raise BadRequestError.
  * If the client sent `Expect: 100-continue`, the server calls `handle_expect_100_continue`, which by default returns CONTINUE.
    At this stage body fields are not yet filled; accessing them raises AttributeError.
  * The server calls `prepare`, which reads the body (if any), fills body fields, and performs final validation:
    duplicate params across sources, excess body params, missing required fields.
  * The server calls `handle_request`, which subclasses must implement to return a Response.
  '''

  max_body_bytes:ClassVar[int] = 0 # Must be overridden by subclasses that expect body parameters.

  _field_transtructors:ClassVar[dict[str,TranstructFn[Any]]]
  _prefigures:ClassVar[dict[type,PrefigureFn]]

  path_params:Mapping[str,object]

  _fill_param_sources:dict[str,str]


  def __init_subclass__(cls, **kwargs:Any) -> None:
    super().__init_subclass__(**kwargs)

    # Build a per-class transtructor seeded with module-level defaults, then layer in _prefigures from the MRO.
    ttor = Transtructor()
    ttor.prefigures.update(endpoint_transtructor.prefigures)
    for base in reversed(cls.__mro__):
      if base is Endpoint: continue
      for type_, fn in base.__dict__.get('_prefigures', {}).items():
        ttor.prefigures[type_] = fn

    fields:dict[str,TranstructFn[Any]] = {}
    for name, hint in get_type_hints(cls).items():
      if name.startswith('_') or name in _endpoint_annotations or get_origin(hint) is ClassVar: continue
      fields[name] = ttor.transtructor_for(hint)
    cls._field_transtructors = fields


  def __init__(self, request:Request, path_params:Mapping[str,object]) -> None:
    '''
    Fill fields from path and query params. Body fields are filled later by `prepare`.
    Raises BadRequestError for duplicate, excess, or unconvertible params.
    '''
    self.path_params = path_params
    self._fill_param_sources = {}
    for name, raw in path_params.items():
      self._fill_param(name=name, raw=raw, source='path')
    for name, raw in request.query.items():
      self._fill_param(name=name, raw=raw, source='query')


  def handle_expect_100_continue(self, request:Request) -> Response:
    '''
    Handle the `Expect: 100-continue` header.
    Path and query params have already been validated during construction,
    so by default this returns CONTINUE to allow the client to send the body.
    '''
    return Response(status=HTTPStatus.CONTINUE)


  def prepare(self, request:Request) -> None:
    '''
    Fill body params and perform final validation.
    Raises BadRequestError on excess body params, duplicate params across sources, or missing required fields.
    '''
    # Fill body fields.
    if request.media_type:
      for name, raw in request.body_params(self.max_body_bytes).items():
        self._fill_param(name=name, raw=raw, source='body')

    # Check for missing fields; let the transtructor determine if None is acceptable.
    for name, transtructor in self._field_transtructors.items():
      if hasattr(self, name): continue
      try: setattr(self, name, transtructor(None, None))
      except (ValueError, TypeError, TranstructorError):
        raise BadRequestError(f'Missing required parameter: {name!r}.')


  def handle_request(self, request:Request) -> Response:
    raise NotImplementedError


  def _fill_param(self, name:str, raw:object, source:str) -> None:
    if prev_source := self._fill_param_sources.get(name):
      raise BadRequestError(f'Duplicate parameter {name!r} in {prev_source} and {source}.')
    transtructor = self._field_transtructors.get(name)
    if transtructor is None:
      raise BadRequestError(f'Unknown parameter {name!r} in {source}.')
    self._fill_param_sources[name] = source

    try:
      setattr(self, name, transtructor(raw, None))
    except (ValueError, TypeError, TranstructorError) as e:
      raise BadRequestError(f'Invalid value for parameter {name!r}: {raw!r}.') from e


# Declare module-level transtructor that can be imported and extended by endpoint consumers if
# there's desired behavior for all endpoints.
endpoint_transtructor = Transtructor()

# Used so we can reliably ignore fields set on endpoint class.
_endpoint_annotations = frozenset(get_annotations(Endpoint).keys())

@endpoint_transtructor.prefigure(list)
def _prefigure_list(cls:type, val:Any, ctx:Any) -> list:
  if isinstance(val, str): return [val]
  return val

@endpoint_transtructor.prefigure(date)
def _prefigure_date(cls:type, val:Any, ctx:Any) -> date:
  if isinstance(val, date) and not isinstance(val, datetime): return val
  return date.fromisoformat(val)


@endpoint_transtructor.prefigure(time)
def _prefigure_time(cls:type, val:Any, ctx:Any) -> time:
  if isinstance(val, time): return val
  return time.fromisoformat(val)


@endpoint_transtructor.prefigure(datetime)
def _prefigure_datetime(cls:type, val:Any, ctx:Any) -> datetime:
  if isinstance(val, datetime): return val
  return datetime.fromisoformat(val)

# This is here so that JSON dicts with the exact keys as UploadedFile dataclass
# don't silently get converted.
@endpoint_transtructor.prefigure(UploadedFile)
def _prefigure_uploaded_file(cls:type, val:Any, ctx:Any) -> UploadedFile:
  if isinstance(val, UploadedFile): return val
  raise ValueError(f'Expected a file upload, got {type(val).__name__!r}.')
