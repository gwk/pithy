# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from http import HTTPStatus
from inspect import get_annotations
from types import GenericAlias, UnionType
from typing import Any, ClassVar, get_args, get_origin

from ..http import endpoint_methods
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



class NoFields:
  'Default fields class for endpoints that declare no inner Fields class.'



class Endpoint(RequestHandler):
  '''
  Base class for request endpoints. An Endpoint instance is created for each request.

  Subclasses declare an inner `Fields` class whose typed annotations are automatically populated from request
  parameters (path, query, body). A fresh `Fields` instance is created per request and exposed as `self.fields`.
  The field types determine how raw values are converted.

  The inner `Fields` class must derive directly from object, making it a pure data holder:
  its namespace contains no framework names, so every annotated name in its body is a field,
  including underscore-prefixed names such as `_debug`. Fields are collected from the `Fields` class body only.
  A subclass that declares `Fields` must also annotate `fields:Fields` so that static type checkers see the
  precise type of `self.fields`; this is enforced at class definition time.
  Any other public annotation in the endpoint class body raises TypeError,
  because it is most likely a field mistakenly declared outside of `Fields`.

  Subclasses must derive directly from Endpoint; defining an intermediate Endpoint subclass raises TypeError.
  Converters are collected from the class body only.

  Use `T|None` to mark a field as optional (None if the parameter is absent).
  Use `list[T]` to collect multiple values for one key (e.g. multi-select).
  Use `list[T]|None` for an optional multi-value field (None if no values are submitted).

  For each field, value conversion of raw request data is handled by a per-class Transtructor or a custom per-field converter.

  To customize conversion for a specific field, define `converters` in the endpoint class body as a class variable
  mapping field names to converter callables of the form `(raw) -> value`:
    class MyEndpoint(Endpoint):
      converters = dict(my_field=lambda raw: MyType.from_string(raw))
      class Fields:
        my_field:MyType
      fields:Fields
  To share converters across endpoints, compose module-level dicts in the class body,
  e.g. `converters = common_converters | dict(...)`.

  To customize conversion by type, register prefigure/selector functions on the endpoint class after its body:
    @MyEndpoint.prefigure(MyType)
    def _prefigure_my_type(cls:type, val:Any, ctx:Any) -> Any: ...
  Each subclass that registers a customization gets its own private Transtructor;
  uncustomized subclasses share a common default, so customizations never affect other endpoints.
  Field converters are resolved lazily when the class first handles a request;
  registering a customization after that point raises TypeError.

  Set `body_field` to the name of a single declared field to fill that field with the entire parsed request body,
  rather than treating the body as a mapping of parameter names to values.
  This is an escape hatch for when the body is best represented as a single object,
  e.g. a JSON array or scalar body, or a top-level object that requires custom interpretation.
  In particular, it allows conversion to be configured for the top-level body type,
  either by registering prefigure/selector functions via the classmethod decorators,
  or by supplying a `converters` entry for the field that wraps its own Transtructor.
  For JSON bodies this lifts the requirement that the body be an object;
  for urlencoded and multipart bodies the field receives the whole params dict.
  Other declared fields are still filled from path and query params as usual;
  a path or query param sharing the body field's name raises a duplicate-param error.

  All Endpoint classes take the following constructor parameters:
  * `request:Request`
  * `path_params:dict[str,object]`

  Request handling flow:
  * The server constructs the endpoint, which creates `self.fields` and fills it from path and query params.
    Duplicates across path and query, excess params not corresponding to fields, and conversion failures raise BadRequestError.
  * If the client sent `Expect: 100-continue`, the server calls `handle_expect_100_continue`, which by default returns CONTINUE.
    At this stage body fields are not yet filled; accessing them on `self.fields` raises AttributeError.
  * The server calls `prepare`, which reads the body (if any), fills body fields, and performs final validation:
    duplicate params across sources, excess body params, missing required fields.
  * The server calls `handle_request`, which subclasses must implement to return a Response.
  '''

  max_body_bytes:ClassVar[int] = 0 # Must be overridden by subclasses that expect body parameters.

  methods:ClassVar[str|Iterable[str]] = 'GET' # Accepted HTTP methods; normalized to _methods by __init_subclass__.
  _methods:ClassVar[frozenset[str]] = frozenset({'GET'})

  # Top-level customization: per-field-name converters, collected from the class body only. Signature: (raw) -> value.
  # A field-specific override may wrap its own Transtructor if the shared default is insufficient.
  converters:ClassVar[dict[str,Callable[[object],object]]] = {}

  body_field:ClassVar[str] = '' # If specified, the whole parsed request body fills the single field of this name.

  # Private per-subclass Transtructor, created lazily by the prefigure/selector classmethods.
  # Subclasses with no customizations leave this None and resolve against the shared default.
  _transtructor:ClassVar[Transtructor|None] = None

  # Set per-subclass once field converters have been resolved; customization is an error afterwards.
  _converters_resolved:ClassVar[bool] = False

  # Built by __init_subclass__ from the inner Fields class body.
  _fields:ClassVar[dict[str,_FieldInfo]]

  # The class used to create the per-request `fields` instance: the inner Fields class, set by __init_subclass__.
  _fields_class:ClassVar[type[Any]] = NoFields

  # The per-request fields instance. Subclasses that declare an inner Fields class re-annotate this as `fields:Fields`.
  fields:Any

  _fill_param_sources:dict[str,str]


  def __init_subclass__(cls, **kwargs:Any) -> None:
    super().__init_subclass__(**kwargs)

    for base in cls.__bases__:
      if issubclass(base, Endpoint) and base is not Endpoint:
        raise TypeError(
          f'{cls.__qualname__}: Endpoint subclasses must derive directly from Endpoint; {base.__qualname__} is an intermediate Endpoint subclass.')

    cls_annotations = get_annotations(cls)
    for name, hint in cls_annotations.items():
      if name == 'fields' or name.startswith('_') or hint is ClassVar or get_origin(hint) is ClassVar: continue
      raise TypeError(
        f'{cls.__qualname__}.{name}: unexpected public annotation in Endpoint subclass body; declare request fields in the inner Fields class.')

    fields_class:type[Any] = cls.__dict__.get('Fields', NoFields)
    if fields_class is NoFields:
      if 'fields' in cls_annotations:
        raise TypeError(f'{cls.__qualname__}: `fields` annotation is present but no inner Fields class is declared.')
    else:
      if not isinstance(fields_class, type) or fields_class.__bases__ != (object,):
        raise TypeError(f'{cls.__qualname__}.Fields must be a class deriving directly from object.')
      if cls_annotations.get('fields') is not fields_class:
        raise TypeError(f'{cls.__qualname__}: declare `fields:Fields` so that the fields instance is precisely typed.')
    cls._fields_class = fields_class

    # Converters are collected from their class bodies only; bases and mixins do not contribute.
    converters:dict[str,Callable[[object],object]] = cls.__dict__.get('converters', {})

    fields:dict[str,_FieldInfo] = {}
    for name, hint in get_annotations(fields_class).items():
      if hint is ClassVar or get_origin(hint) is ClassVar: continue
      element_type, is_optional, is_list = _unwrap_field_type(hint)
      # Per-field converters bind now; transtructor-backed converters resolve lazily on the first request,
      # so that prefigure/selector customizations registered after the class body are honored.
      fields[name] = _FieldInfo(name=name, type=element_type, is_optional=is_optional, is_list=is_list,
        convert=converters.get(name))
    cls._fields = fields

    if cls.body_field and cls.body_field not in fields:
      raise TypeError(f'{cls.__qualname__}: body_field {cls.body_field!r} does not name a declared field.')

    methods_val = cls.methods
    method_set:set[str] = {methods_val} if isinstance(methods_val, str) else set(methods_val)
    if not method_set:
      raise TypeError(f'{cls.__qualname__}: methods must not be empty.')
    for m in method_set:
      if m not in endpoint_methods:
        raise TypeError(f'{cls.__qualname__}: invalid HTTP method {m!r}; valid endpoint methods are {sorted(endpoint_methods)}.')
    cls._methods = frozenset(method_set)


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
    Create the fields instance and fill it from path and query params. Body fields are filled later by `prepare`.
    Raises BadRequestError for duplicate, excess, or unconvertible params.
    '''
    cls = type(self)
    if not cls._converters_resolved: cls._resolve_converters()
    self.fields = cls._fields_class()
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
      for name, raw in request.body_params(self.max_body_bytes, body_field=self.body_field).items():
        self._fill_param(name=name, raw=raw, source='body')
    for name, field in self._fields.items():
      if hasattr(self.fields, name): continue
      if not field.is_optional:
        raise BadRequestError(f'Missing required parameter: {name!r}.')
      setattr(self.fields, name, None)


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
        setattr(self.fields, name, [convert(el) for el in items])
      else:
        setattr(self.fields, name, convert(raw))
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
