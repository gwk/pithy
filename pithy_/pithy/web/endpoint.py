# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import types
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from http import HTTPStatus
from typing import Any, ClassVar, get_args, get_origin, get_type_hints

from pithy.type_utils import is_a

from ..transtruct import bool_str_vals
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

  To add custom type converters, define `_converters` as a class variable mapping types to callables:
    class MyEndpoint(Endpoint):
      _converters = {MyType: MyType.from_string}
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

  _fields:ClassVar[dict[str,_FieldInfo]]
  _converters:ClassVar[dict[type,Any]]

  path_params:Mapping[str,object]

  _fill_param_sources:dict[str,str]


  def __init_subclass__(cls, **kwargs:Any) -> None:
    super().__init_subclass__(**kwargs)

    # Build converters: start with defaults, layer in any _converters defined on classes in the MRO.
    converters:dict[type,Any] = dict(_default_converters)
    for base in reversed(cls.__mro__):
      if base is Endpoint: continue
      base_conv = base.__dict__.get('_converters')
      if base_conv:
        converters.update(base_conv)
    cls._converters = converters

    # Introspect type hints to build field metadata.
    hints = get_type_hints(cls)
    fields:dict[str,_FieldInfo] = {}
    for name, hint in hints.items():
      if name.startswith('_'): continue
      base_type, is_optional = _unwrap_optional(hint)
      inner = base_type if base_type is not None else hint
      is_list = get_origin(inner) is list
      if is_list:
        base_type = get_args(inner)[0]
      if base_type is None: continue
      converter = converters.get(base_type)
      if converter is None:
        raise TypeError(f'{cls.__qualname__}.{name}: no converter registered for type {base_type!r}.')
      fields[name] = _FieldInfo(name=name, type=base_type, is_optional=is_optional, is_list=is_list, converter=converter)
    cls._fields = fields


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

    # Check for missing required fields and set optional fields to None.
    for name, field in self._fields.items():
      if hasattr(self, name): continue
      if not field.is_optional:
        raise BadRequestError(f'Missing required parameter: {name!r}.')
      setattr(self, name, None)


  def handle_request(self, request:Request) -> Response:
    raise NotImplementedError


  def _fill_param(self, name:str, raw:object, source:str) -> None:
    if prev_source := self._fill_param_sources.get(name):
      raise BadRequestError(f'Duplicate parameter {name!r} in {prev_source} and {source}.')
    field = self._fields.get(name)
    if field is None:
      raise BadRequestError(f'Unknown parameter {name!r} in {source}.')
    self._fill_param_sources[name] = source

    # list fields
    if field.is_list:
      if not isinstance(raw, list): raw = [raw]
      if is_a(raw, list[field.type]):  # type: ignore[name-defined]
        setattr(self, field.name, raw)
        return
      try:
        setattr(self, field.name, [field.converter(r) for r in raw])
      except (ValueError, TypeError) as e:
        raise BadRequestError(f'Invalid value for parameter {name!r}: {raw!r}.') from e
      return

    # scalar fields
    if isinstance(raw, field.type):
      setattr(self, field.name, raw)
      return
    try:
      setattr(self, field.name, field.converter(raw))
    except (ValueError, TypeError) as e:
      raise BadRequestError(f'Invalid value for parameter {name!r}: {raw!r}.') from e


@dataclass(slots=True, frozen=True)
class _FieldInfo:
  'Metadata for a single declared field on an Endpoint subclass.'
  name: str
  type: type
  is_optional: bool
  is_list: bool
  converter: Any


def _unwrap_optional(hint:Any) -> tuple[type|None,bool]:
  'Extract the base type and whether the hint is optional (T | None). Returns (None, False) for unsupported hints.'
  origin = get_origin(hint)
  if origin is types.UnionType:
    args = get_args(hint)
    non_none = [a for a in args if a is not type(None)]
    if type(None) in args and len(non_none) == 1:
      return (non_none[0], True)
    return (None, False)
  if isinstance(hint, type):
    return (hint, False)
  return (None, False)


def _parse_bool(s:str) -> bool:
  try: return bool_str_vals[s]
  except KeyError: raise ValueError(f'Invalid bool value: {s!r}.')


def _require_uploaded_file(x:Any) -> UploadedFile:
  raise ValueError(f'Expected a file upload, got {type(x).__name__!r}.')


_default_converters:dict[type,Any] = {
  str: str,
  int: int,
  float: float,
  bool: _parse_bool,
  date: date.fromisoformat,
  time: time.fromisoformat,
  datetime: datetime.fromisoformat,
  UploadedFile: _require_uploaded_file,
}
