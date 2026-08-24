# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from annotationlib import Format
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from http import HTTPStatus
from inspect import get_annotations, Parameter, signature
from typing import Any, ClassVar, get_args, get_origin, Literal, Union

from typing_extensions import TypeForm

from ..http import endpoint_methods
from ..transtruct import PrefigureFn, SelectorFn, TranstructFn, Transtructor, TranstructorError
from ..type_utils import FixedStrSet, NoneType, nonopt_type, normalize_type_form, req_type
from .errors import BadRequestError
from .handler import RoutableHandler
from .request import Request, UploadedFile
from .requestconn import BodyTooLargeError
from .response import Response


@dataclass(slots=True, frozen=True)
class _FieldInfo:
  name:str
  field_type:TypeForm[Any] # The declared field type form, normalized; drives conversion and validates converted values.
  is_optional:bool
  is_list:bool
  convert:Callable[[object],object]|None # Whole-field converter; None until lazily resolved against the transtructor.



class NoFields:
  'Default fields class for endpoints that declare no inner Fields class.'



class Endpoint(RoutableHandler):
  '''
  Base class for request endpoints. An Endpoint instance is created for each request.

  # Fields

  Subclasses declare an inner `Fields` class whose fields are populated from request path, query, and body parameters.
  A fresh `Fields` instance is created per request and passed to `handle_endpoint`.
  The declared field types determine how raw values are converted.

  The inner `Fields` class must derive directly from `object`.
  Its namespace contains no framework names, so every annotated name in its body is a field,
  including names with leading underscores.

  The `fields` parameter of `handle_endpoint` must be annotated with the exact inner `Fields` class.
  This gives endpoint implementations a precisely typed fields value without exposing it as endpoint machinery.
  An endpoint that accesses `self.fields` in other methods may additionally declare `fields:Fields` in its class body.
  This optional declaration gives those accesses the precise type; without it, `self.fields` is typed as `object`.

  Any other public field annotation in the endpoint class body raises TypeError,
  because it is most likely a field mistakenly declared outside of `Fields`.

  Subclasses must derive directly from Endpoint; defining an intermediate Endpoint subclass raises TypeError.

  Field types are type forms (PEP 747), so Literal, union and type alias type forms are accepted and enforced.
  A value outside of a required literal set is rejected.

  ## Optional and Multi-value Fields

  For each field, the outermost type form determines the HTTP parameter validation:
  * `T|None` marks the field as optional (None if the parameter is absent or an explicit JSON null);
  * `list[T]` marks it as multi-value, collecting every value submitted for its key (e.g. multi-select).
  * `list[T]|None` is an optional multi-value field (None if no values are submitted).

  ## Unions

  For form data, all incoming fields are either raw strings or file uploads.
  Union types as supported by Transtructor are of limited value for string fields: `str|int` will always pass through the `str`.
  Unions are more generally applicable for JSON body fields.
  See `Transtructor` for the full details of union type conversion.

  ## Converters

  For each field, value conversion of raw request data is handled by either a per-class Transtructor or a per-field converter.
  The converter receives the whole field input and converts it to the full declared field type.
  For a multi-value field, a single submitted value is first wrapped into a one-element list,
  so the converter always receives a list (or None from an explicit JSON null).

  To customize conversion for a specific field, define a `converters` dict in the endpoint class body as a class variable
  mapping field names to converter callables of the form `(raw) -> value`:
    class MyEndpoint(Endpoint):
      class Fields:
        my_field:MyType
      def handle_endpoint(self, request:Request, fields:Fields) -> Response: ...
      converters = dict(my_field=lambda raw: MyType.from_string(raw))
  To share converters across endpoints, compose module-level dicts in the class body,
  e.g. `converters = common_converters | dict(...)`.

  Every converted field value is checked against the declared field type with `req_type`.
  A mismatch indicates a defective converter and raises TypeError, which surfaces as a server error.
  A converter for an optional field may legitimately return None, since the declared type admits it.

  ## Transtructors

  In the absence of a custom converter, a per-class Transtructor is used.

  To customize conversion by type, register prefigure/selector functions on the endpoint class after its body:
    @MyEndpoint.prefigure(MyType)
    def _prefigure_my_type(cls:TypeForm[Any], val:Any, ctx:Any) -> Any: ...
  Each subclass that registers a customization gets its own private Transtructor;
  uncustomized subclasses share a common default, so customizations never affect other endpoints.
  Field converters are resolved when the endpoint is registered with a Router, or otherwise when it first handles a request;
  registering a customization after that point raises TypeError.
  Registration resolves converters so that an unconstructible field type is reported at startup
  rather than by the first request to that route.

  ## Whole-body Transtruction

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

  # Lifecycle

  All Endpoint classes take the following constructor parameters:
  * `request:Request`
  * `path_params:dict[str,object]`

  Request handling flow:
  * The server constructs the endpoint, which creates its internal fields object and fills it from path and query params.
    Duplicates across path and query, excess params not corresponding to fields, and conversion failures raise BadRequestError.
  * If the client sent `Expect: 100-continue`, the server calls `handle_expect_100_continue`, which by default returns CONTINUE.
    At this stage body fields are not yet filled.
  * The server calls `prepare`, which reads the body (if any), fills body fields, and performs final validation:
    duplicate params across sources, excess body params, missing required fields.
  * The server calls `handle_request`, which dispatches to the subclass's `handle_endpoint` implementation.
  '''

  max_body_bytes:ClassVar[int] = 0 # Must be overridden by subclasses that expect body parameters.

  methods:ClassVar[FixedStrSet] = 'GET' # Accepted HTTP methods; normalized to _methods by __init_subclass__.

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

  # The internal per-request fields instance. Subclasses may redeclare this with their precise Fields type when needed.
  fields:object

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
    if fields_class is not NoFields and (not isinstance(fields_class, type) or fields_class.__bases__ != (object,)):
      raise TypeError(f'{cls.__qualname__}.Fields must be a class deriving directly from object.')
    if (fields_annotation := cls_annotations.get('fields')) is not None:
      if fields_annotation is not fields_class:
        raise TypeError(f'{cls.__qualname__}.fields must be annotated as {fields_class.__qualname__}.')
    _validate_handle_endpoint(cls, fields_class)
    cls._fields_class = fields_class

    # Converters are collected from their class bodies only; bases and mixins do not contribute.
    converters:dict[str,Callable[[object],object]] = cls.__dict__.get('converters', {})

    fields:dict[str,_FieldInfo] = {}
    for name, hint in get_annotations(fields_class).items():
      if hint is ClassVar or get_origin(hint) is ClassVar: continue
      field_type, is_optional, is_list = _unwrap_field_type(hint)
      # Per-field converters bind now; transtructor-backed converters resolve lazily on the first request,
      # so that prefigure/selector customizations registered after the class body are honored.
      fields[name] = _FieldInfo(name=name, field_type=field_type, is_optional=is_optional, is_list=is_list,
        convert=converters.get(name))
    cls._fields = fields

    if cls.body_field and cls.body_field not in fields:
      raise TypeError(f'{cls.__qualname__}: body_field {cls.body_field!r} does not name a declared field.')

    methods_raw = cls.methods
    methods:frozenset[str] = frozenset((methods_raw,) if isinstance(methods_raw, str) else methods_raw)
    if not methods:
      raise TypeError(f'{cls.__qualname__}: methods must not be empty.')
    for m in methods:
      if m not in endpoint_methods:
        raise TypeError(f'{cls.__qualname__}: invalid HTTP method {m!r}; valid endpoint methods are {sorted(endpoint_methods)}.')
    cls._methods = frozenset(methods)


  @classmethod
  def prefigure(cls, datatype:type) -> Callable[[PrefigureFn],PrefigureFn]:
    '''
    Decorator factory that registers a prefigure function on this endpoint subclass private Transtructor.
    Usage: `@MyEndpoint.prefigure(SomeType)`. Must be called before the class's field converters are resolved,
    which happens when the endpoint is registered with a Router, or otherwise when it first handles a request.
    '''
    return cls._customizable_transtructor().prefigure(datatype)


  @classmethod
  def selector(cls, datatype:TypeForm[Any]) -> Callable[[SelectorFn],SelectorFn]:
    '''
    Decorator factory that registers a selector function on this endpoint subclass private Transtructor.
    Usage: `@MyEndpoint.selector(SomeType)`. Must be called before the class's field converters are resolved,
    which happens when the endpoint is registered with a Router, or otherwise when it first handles a request.
    `datatype` may be a union type form, e.g. `@MyEndpoint.selector(Circle|Rect)`;
    this is required for a field whose type is a union with more than one non-primitive member.
    '''
    return cls._customizable_transtructor().selector(datatype)


  @classmethod
  def _customizable_transtructor(cls) -> Transtructor:
    'Return this subclass private Transtructor for customization, creating it on first access.'
    if cls is Endpoint:
      raise TypeError('Customize a specific Endpoint subclass, not Endpoint itself.')
    if cls._converters_resolved:
      raise TypeError(f'{cls.__qualname__}: cannot customize the transtructor after its field converters are resolved.')
    transtructor = cls.__dict__.get('_transtructor')
    if transtructor is None:
      transtructor = _new_endpoint_transtructor()
      cls._transtructor = transtructor
    return transtructor


  @classmethod
  def _resolve_converters(cls) -> None:
    '''
    Resolve transtructor-backed field converters against the private or shared Transtructor.
    Deferred past the class body so that prefigure/selector customizations registered after it
    (via the classmethod decorators) are honored. The Router resolves every registered endpoint at construction,
    so that an unconstructible field type fails at startup rather than on the first request to that route.
    Idempotent; a concurrent first-request race is benign.
    '''
    if cls._converters_resolved: return
    transtructor = cls.__dict__.get('_transtructor') or _shared_endpoint_transtructor
    fields:dict[str,_FieldInfo] = {}
    for name, field in cls._fields.items():
      if field.convert is None:
        # Security boundary: transtruct is only ever invoked on the declared field type, never on the Endpoint/handler type.
        # Do not "simplify" this into transtructing the whole endpoint.
        try: transtruct_fn = transtructor.transtructor_for(field.field_type)
        except (TypeError, TranstructorError) as e:
          raise TypeError(
            f'{cls.__qualname__}.Fields.{name}: no converter is available for field type {field.field_type!r}.') from e
        field = replace(field, convert=_transtruct_converter(transtruct_fn))
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
    for name, vals in request.query_multi.items():
      # Match the shape of the form body parsers: a single value is a scalar, repeated values are a list.
      # A repeated key for a non-list field then fails conversion, just as it would in a form body.
      self._fill_param(name=name, raw=(vals if len(vals) > 1 else vals[0]), source='query')

    if request.content_length is not None and request.content_length > self.max_body_bytes:
      # Reject a declared body that exceeds the declared max before it is read.
      raise BodyTooLargeError(length=request.content_length, max_bytes=self.max_body_bytes)


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
    return self.handle_endpoint(request, self.fields)


  def handle_endpoint(self, request:Request, fields:Any) -> Response:
    'Handle the prepared request with its precisely typed fields object. Subclasses must override this method.'
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
    if field.is_list and not isinstance(raw, list) and raw is not None:
      # A single submitted value fills a multi-value field as a one-element list.
      # This normalization must precede conversion: transtruct would iterate a bare str into its characters.
      # None (an explicit JSON null) is preserved for the field type union to accept or reject.
      raw = [raw]
    try: converted_value = convert(raw)
    except (ValueError, TypeError, TranstructorError) as e:
      # Truncate the raw value so that a large or whole-body value is not reflected back in the error response.
      raise BadRequestError(f'Invalid value for parameter {name!r}: {repr(raw)[:64]}.') from e
    # Validate outside of the try clause above, so that a converter returning a mistyped value raises TypeError (500).
    setattr(self.fields, name, req_type(converted_value, field.field_type))


def _transtruct_converter(tf:TranstructFn[Any]) -> Callable[[object],object]:
  'Adapt a transtruct function into a field converter of the form `(raw) -> value`.'
  return lambda raw: tf(raw, None)


def _unwrap_field_type(hint:TypeForm[Any]) -> tuple[TypeForm[Any],bool,bool]:
  '''
  Analyze an endpoint field type form hint into (field_type, is_optional, is_list).
  `field_type` is the normalized declared type; it drives conversion and converted values are validated against it.
  Only the outermost type form sets the optional and list flags; see the Endpoint class docstring for the field type rules.
  The unwrapped element type is checked for developer errors but not returned; conversion operates on the full field type.
  '''
  field_type = normalize_type_form(hint)
  hint = field_type
  is_optional = False
  if get_origin(hint) is Union and NoneType in get_args(hint):
    # The unwrapping here only determines the HTTP semantics flags and exposes the inner types for checking;
    # the full field type, including the optional and list forms, is what gets converted and validated.
    is_optional = True
    hint = normalize_type_form(nonopt_type(hint))
  is_list = get_origin(hint) is list
  if is_list:
    args = get_args(hint)
    if len(args) != 1: raise TypeError(f'incorrect list field type: {hint!r}') # Python accepts e.g. `list[int,str]` at runtime.
    hint = normalize_type_form(args[0])
  _check_field_type(hint)
  return (field_type, is_optional, is_list)


def _check_field_type(hint:TypeForm[Any]) -> None:
  '''
  Raise TypeError for normalized element type forms that make no sense as endpoint fields.
  The transtructor is otherwise the authority on which type forms are constructible: it raises for the rest,
  and that error surfaces when field converters are resolved.
  Type forms whose origin is callable (covering both `Callable[...]` and `type[T]`) are rejected here
  because the transtructor accepts them but they are developer errors for an endpoint:
  a `Callable[...]` field would reject every request at runtime, since request values are never callable,
  and a `type[T]` field would let the client choose a Python type by name (see `transtruct.named_types`).
  Type forms that are neither classes nor recognized generic or special type forms are also rejected here,
  so that the error is raised at class definition and names the offending annotation.
  Union members are checked recursively; other nested type arguments (e.g. of a list or dict) are validated by
  the transtructor when it builds the converter.
  '''
  origin = get_origin(hint)
  if origin is None:
    if isinstance(hint, type): return # A plain class; the transtructor decides whether it is constructible.
    raise TypeError(f'unsupported field type: {hint!r}')
  if origin is Union:
    for member in get_args(hint): _check_field_type(normalize_type_form(member))
    return
  if origin is Literal: return
  if isinstance(origin, type):
    if issubclass(origin, Callable): # type: ignore[arg-type] # collections.abc.Callable is accepted by issubclass.
      raise TypeError(f'unsupported field type: {hint!r}; callable types cannot be constructed from request params.')
    return
  raise TypeError(f'unsupported field type: {hint!r}')


def _new_endpoint_transtructor() -> Transtructor:
  'Create a Transtructor with the built-in endpoint guards installed.'
  transtructor = Transtructor(strict=False)

  @transtructor.prefigure(UploadedFile) # Prevent silent construction from a JSON dict with matching keys.
  def _prefigure_uploaded_file(cls:TypeForm[Any], val:Any, ctx:Any) -> Any:
    if isinstance(val, UploadedFile): return val
    raise ValueError(f'Expected a file upload, got {type(val).__name__!r}.')

  return transtructor


# Private shared transtructor used by endpoint subclasses that register no prefigure/selector customizations.
_shared_endpoint_transtructor = _new_endpoint_transtructor()


def _validate_handle_endpoint(cls:type[Endpoint], fields_class:type[Any]) -> None:
  'Validate a concrete Endpoint subclass hook at class definition time.'
  if 'handle_request' in cls.__dict__:
    raise TypeError(f'{cls.__qualname__}: override `handle_endpoint`, not framework method `handle_request`.')
  handler = cls.__dict__.get('handle_endpoint')
  if handler is None:
    raise TypeError(f'{cls.__qualname__}: define `handle_endpoint(self, request, fields)`.')
  if not callable(handler):
    raise TypeError(f'{cls.__qualname__}.handle_endpoint must be a method.')
  params = tuple(signature(handler, annotation_format=Format.STRING).parameters.values())
  if len(params) != 3 or any(p.kind is not Parameter.POSITIONAL_OR_KEYWORD for p in params):
    raise TypeError(f'{cls.__qualname__}.handle_endpoint must have signature `(self, request, fields)`.')
  if tuple(p.name for p in params) != ('self', 'request', 'fields'):
    raise TypeError(f'{cls.__qualname__}.handle_endpoint parameter names must be `(self, request, fields)`.')
  if any(p.default is not Parameter.empty for p in params):
    raise TypeError(f'{cls.__qualname__}.handle_endpoint parameters must not have defaults.')
  try: annotations = get_annotations(handler)
  except (NameError, TypeError) as e:
    raise TypeError(f'{cls.__qualname__}.handle_endpoint annotations could not be evaluated: {e}') from e
  if annotations.get('request') is not Request:
    raise TypeError(f'{cls.__qualname__}.handle_endpoint.request must be annotated as Request.')
  if annotations.get('fields') is not fields_class:
    expected = fields_class.__qualname__
    raise TypeError(f'{cls.__qualname__}.handle_endpoint.fields must be annotated as {expected}.')
  response_type = annotations.get('return')
  if not isinstance(response_type, type) or not issubclass(response_type, Response):
    raise TypeError(f'{cls.__qualname__}.handle_endpoint return must be annotated as Response or a Response subclass.')
