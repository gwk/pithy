# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from http import HTTPStatus
from inspect import get_annotations
from types import GenericAlias, UnionType
from typing import Any, ClassVar, get_args, get_origin

from ..transtruct import PrefigureFn, SelectorFn, TranstructFn, Transtructor, TranstructorError
from .errors import BadRequestError
from .handler import RequestHandler
from .request import Request, UploadedFile
from .response import Response


@dataclass(slots=True, frozen=True)
class _FieldInfo:
  name:str
  type:type # Element type, after unwrapping optional/list.
  is_optional:bool
  is_list:bool
  convert:Callable[[object],object]|None # Element converter; None until lazily resolved against the transtructor.



class Endpoint(RequestHandler):
  '''
  Base class for request endpoints. An Endpoint instance is created for each request.

  Subclasses declare typed fields that are automatically populated from request parameters (path, query, body).
  The field types determine how raw values are converted.

  Subclasses must derive directly from Endpoint; defining an intermediate Endpoint subclass raises TypeError.
  Fields and `_converters` are collected from the class body only, so that everything an endpoint accepts is
  plainly expressed in one place.

  Use `T|None` to mark a field as optional (None if the parameter is absent).
  Use `list[T]` to collect multiple values for one key (e.g. multi-select).
  Use `list[T]|None` for an optional multi-value field (None if no values are submitted).

  For each field of the Endpoint subclass, value conversion of raw request data is handled by a per-class Transtructor,
  or optionally by a per-field converter.

  To customize conversion for a specific field, define `_converters` as a class variable mapping field names to
  converter callables of the form `(raw) -> value`:
    class MyEndpoint(Endpoint):
      _converters = dict(my_field=lambda raw: MyType.from_string(raw))
      my_field:MyType
  To share converters across endpoints, compose module-level dicts in the class body,
  e.g. `_converters = common_converters | dict(...)`.

  To customize conversion by type, register prefigure/selector functions on the endpoint class after its body:
    @MyEndpoint.prefigure(MyType)
    def _prefigure_my_type(cls:type, val:Any, ctx:Any) -> Any: ...
  Each subclass that registers a customization gets its own private Transtructor;
  uncustomized subclasses share a common default, so customizations never affect other endpoints.
  Field converters are resolved lazily when the class first handles a request;
  registering a customization after that point raises TypeError.

  Set `_body_field` to the name of a single declared field to fill that field with the entire parsed request body,
  rather than treating the body as a mapping of parameter names to values.
  This is an escape hatch for when the body is best represented as a single object,
  e.g. a JSON array or scalar body, or a top-level object that requires custom interpretation.
  In particular, it allows conversion to be configured for the top-level body type,
  either by registering prefigure/selector functions via the classmethod decorators,
  or by supplying a `_converters` entry for the field that wraps its own Transtructor.
  For JSON bodies this lifts the requirement that the body be an object;
  for urlencoded and multipart bodies the field receives the whole params dict.
  Other declared fields are still filled from path and query params as usual;
  a path or query param sharing the body field's name raises a duplicate-param error.

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

  # Top-level customization: per-field-name converters, collected from the class body only. Signature: (raw) -> value.
  # A field-specific override may wrap its own Transtructor if the shared default is insufficient.
  _converters:ClassVar[dict[str,Callable[[object],object]]] = {}

  # When non-empty, the whole parsed request body fills the single field of this name (any media type).
  _body_field:ClassVar[str] = ''

  # Private per-subclass Transtructor, created lazily by the prefigure/selector classmethods.
  # Subclasses with no customizations leave this None and resolve against the shared default.
  _transtructor:ClassVar[Transtructor|None] = None

  # Set per-subclass once field converters have been resolved; customization is an error afterwards.
  _converters_resolved:ClassVar[bool] = False

  # Built by __init_subclass__.
  _fields:ClassVar[dict[str,_FieldInfo]]

  path_params:Mapping[str,object]

  _fill_param_sources:dict[str,str]


  def __init_subclass__(cls, **kwargs:Any) -> None:
    super().__init_subclass__(**kwargs)

    for base in cls.__bases__:
      if issubclass(base, Endpoint) and base is not Endpoint:
        raise TypeError(
          f'{cls.__qualname__}: Endpoint subclasses must derive directly from Endpoint; {base.__qualname__} is an intermediate Endpoint subclass.')

    # Converters and fields are collected from the class body only; bases and mixins do not contribute.
    converters:dict[str,Callable[[object],object]] = cls.__dict__.get('_converters', {})

    fields:dict[str,_FieldInfo] = {}
    for name, hint in get_annotations(cls).items():
      if name.startswith('_') or hint is ClassVar or get_origin(hint) is ClassVar: continue
      if name in _endpoint_reserved_names:
        raise TypeError(f'{cls.__qualname__}.{name}: field name shadows an Endpoint base attribute.')
      element_type, is_optional, is_list = _unwrap_field_type(hint)
      # Per-field converters bind now; transtructor-backed converters resolve lazily on the first request,
      # so that prefigure/selector customizations registered after the class body are honored.
      fields[name] = _FieldInfo(name=name, type=element_type, is_optional=is_optional, is_list=is_list,
        convert=converters.get(name))
    cls._fields = fields

    if cls._body_field and cls._body_field not in fields:
      raise TypeError(f'{cls.__qualname__}: _body_field {cls._body_field!r} does not name a declared field.')


  @classmethod
  def prefigure(cls, datatype:type) -> Callable[[PrefigureFn],PrefigureFn]:
    '''
    Decorator factory that registers a prefigure function on this endpoint subclass private Transtructor.
    Usage: `@MyEndpoint.prefigure(SomeType)`. Must be called before the class handles its first request.
    '''
    return cls._customizable_transtructor().prefigure(datatype)


  @classmethod
  def selector(cls, datatype:type) -> Callable[[SelectorFn],SelectorFn]:
    '''
    Decorator factory that registers a selector function on this endpoint subclass private Transtructor.
    Usage: `@MyEndpoint.selector(SomeType)`. Must be called before the class handles its first request.
    '''
    return cls._customizable_transtructor().selector(datatype)


  @classmethod
  def _customizable_transtructor(cls) -> Transtructor:
    'Return this subclass private Transtructor for customization, creating it on first access.'
    if cls is Endpoint:
      raise TypeError('Customize a specific Endpoint subclass, not Endpoint itself.')
    if cls._converters_resolved:
      raise TypeError(f'{cls.__qualname__}: cannot customize the transtructor after the class has handled a request.')
    transtructor = cls.__dict__.get('_transtructor')
    if transtructor is None:
      transtructor = _new_endpoint_transtructor()
      cls._transtructor = transtructor
    return transtructor


  @classmethod
  def _resolve_converters(cls) -> None:
    '''
    Resolve transtructor-backed field converters against the private or shared Transtructor.
    Deferred until the first request so that prefigure/selector customizations registered after the class body
    (via the classmethod decorators) are honored. Idempotent; a concurrent first-request race is benign.
    '''
    transtructor = cls.__dict__.get('_transtructor') or _shared_endpoint_transtructor
    fields:dict[str,_FieldInfo] = {}
    for name, field in cls._fields.items():
      if field.convert is None:
        # Security boundary: transtruct is only ever invoked on the declared field element type, never on the
        # Endpoint (or any handler) type. Do not "simplify" this into transtructing the whole endpoint.
        field = replace(field, convert=_transtruct_converter(transtructor.transtructor_for(field.type)))
      fields[name] = field
    cls._fields = fields
    cls._converters_resolved = True


  def __init__(self, request:Request, path_params:Mapping[str,object]) -> None:
    '''
    Fill fields from path and query params. Body fields are filled later by `prepare`.
    Raises BadRequestError for duplicate, excess, or unconvertible params.
    '''
    cls = type(self)
    if not cls._converters_resolved: cls._resolve_converters()
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
    if request.media_type:
      for name, raw in request.body_params(self.max_body_bytes, body_field=self._body_field).items():
        self._fill_param(name=name, raw=raw, source='body')
    for name, field in self._fields.items():
      if hasattr(self, name): continue
      if not field.is_optional:
        raise BadRequestError(f'Missing required parameter: {name!r}.')
      setattr(self, name, None)


  def handle_request(self, request:Request) -> Response:
    raise NotImplementedError


  def _fill_param(self, name:str, raw:object, source:str) -> None:
    if prev := self._fill_param_sources.get(name):
      raise BadRequestError(f'Duplicate parameter {name!r} in {prev} and {source}.')
    field = self._fields.get(name)
    if field is None:
      raise BadRequestError(f'Unknown parameter {name!r} in {source}.')
    self._fill_param_sources[name] = source
    convert = field.convert
    assert convert is not None # Resolved by _resolve_converters at construction.
    try:
      if field.is_list:
        items = raw if isinstance(raw, list) else [raw]
        setattr(self, name, [convert(el) for el in items])
      else:
        setattr(self, name, convert(raw))
    except (ValueError, TypeError, TranstructorError) as e:
      # Truncate the raw value so that a large or whole-body value is not reflected back in the error response.
      raise BadRequestError(f'Invalid value for parameter {name!r}: {repr(raw)[:64]}.') from e


def _transtruct_converter(tf:TranstructFn[Any]) -> Callable[[object],object]:
  'Adapt a transtruct function into an element converter of the form `(raw) -> value`.'
  return lambda raw: tf(raw, None)


_NoneType = type(None)


def _unwrap_field_type(hint:type|GenericAlias|UnionType) -> tuple[type,bool,bool]:
  '''
  Decompose an endpoint field type hint into (element_type, is_optional, is_list).
  Supports only the shapes that HTTP param semantics dictate: T, T|None, list[T], list[T]|None.
  The optional flag marks a field as not required; the list flag marks a field that accepts multiple values per key.
  Any other shape is rejected as a developer error.
  '''
  is_optional = False
  if isinstance(hint, UnionType):
    args = get_args(hint)
    non_none = [a for a in args if a is not _NoneType]
    if _NoneType not in args or len(non_none) != 1:
      raise TypeError(f'unsupported union field type: {hint!r}')
    is_optional = True
    hint = non_none[0]
  is_list = get_origin(hint) is list
  if is_list:
    args = get_args(hint)
    if len(args) != 1: raise TypeError(f'incorrect list field type: {hint!r}') # Python accepts e.g. `list[int,str]` at runtime.
    hint = args[0]
  if not isinstance(hint, type):
    raise TypeError(f'unsupported field type: {hint!r}')
  return (hint, is_optional, is_list)


def _new_endpoint_transtructor() -> Transtructor:
  'Create a Transtructor with the built-in endpoint guards installed.'
  transtructor = Transtructor()

  @transtructor.prefigure(UploadedFile) # Prevent silent construction from a JSON dict with matching keys.
  def _prefigure_uploaded_file(cls:type, val:Any, ctx:Any) -> Any:
    if isinstance(val, UploadedFile): return val
    raise ValueError(f'Expected a file upload, got {type(val).__name__!r}.')

  return transtructor


# Private shared transtructor used by endpoint subclasses that register no prefigure/selector customizations.
_shared_endpoint_transtructor = _new_endpoint_transtructor()

# Names of Endpoint base attributes and annotations; declared fields must not shadow them.
_endpoint_reserved_names = frozenset(dir(Endpoint)) | frozenset(get_annotations(Endpoint))
