# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from annotationlib import Format
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from http import HTTPStatus
from inspect import get_annotations, Parameter, signature
from typing import Any, ClassVar, get_args, get_origin, Literal, Union

from typing_extensions import TypeForm

from ..default import Default
from ..transtruct import PrefigureFn, SelectorFn, TranstructFn, Transtructor, TranstructorError
from ..type_utils import NoneType, nonopt_type, normalize_type_form, req_type
from .errors import BadRequestError, MethodNotAllowedError
from .handler import RoutableHandler
from .request import Request, UploadedFile
from .requestconn import BodyTooLargeError
from .response import Response


# HTTP methods that an Endpoint subclass handles, mapped to their handler method names.
# The inner fields class for each is the capitalized method name, e.g. `Get`, `Post`.
# HEAD is dispatched to the GET handler and is not a key here.
handler_methods:dict[str,str] = {m: m.lower() for m in ('DELETE', 'GET', 'PATCH', 'POST', 'PUT')}

# Methods whose requests may carry a body. A request body on any other method is rejected at construction.
body_methods:frozenset[str] = frozenset({'PATCH', 'POST', 'PUT'})

# Method names that are reserved so that a subclass does not define one expecting it to be dispatched to.
_reserved_method_names = frozenset({'connect', 'head', 'options', 'trace'})


@dataclass(slots=True, frozen=True)
class _FieldInfo:
  name:str
  field_type:TypeForm[Any] # The declared field type form, normalized; drives conversion and validates converted values.
  is_optional:bool
  is_list:bool
  # Whole-field converters; None until lazily resolved against the transtructor. A custom converter fills both.
  convert_str:Callable[[object],object]|None # For string sources (path, query, form data): transtructs with `blank_to_none=True`.
  convert_typed:Callable[[object],object]|None # For typed sources (JSON): transtructs with `blank_to_none=False`.


@dataclass(slots=True, frozen=True)
class _MethodSpec:
  'The per-HTTP-method handler and fields schema of an Endpoint subclass, built by __init_subclass__.'
  method:str
  handler_name:str
  fields_class:type[Any]
  fields:dict[str,_FieldInfo]



class Endpoint(RoutableHandler):
  '''
  Base class for request endpoints. An Endpoint instance is created for each request.

  # Handler Methods

  Subclasses define a handler method for each HTTP method they accept: `get`, `post`, `put`, `patch` and/or `delete`.
  The accepted methods are derived from the handlers defined; there is no separate methods declaration.
  HEAD requests are accepted whenever `get` is defined and are dispatched to it;
  the server omits the response body. A `get` implementation may check `request.method == 'HEAD'`
  and return a headers-only response early to skip rendering.

  Only PATCH, POST and PUT requests may carry a body; `max_body_bytes` must be set for an endpoint to accept one.
  A GET, HEAD or DELETE request that carries a body is rejected with BadRequestError.

  Each handler has the signature `(self, request:Request, fields:Get) -> Response`,
  where the `fields` annotation is the exact inner fields class for that method (see below), or `None` if none.
  A handler with no fields class receives `None` as its fields argument.

  # Fields

  For each handler, a subclass may declare an inner fields class named for the HTTP method: `Get`, `Post`, `Put`,
  `Patch` or `Delete`. Its fields are populated from request path, query, and body parameters.
  A fresh instance is created per request and passed to the handler.
  The declared field types determine how raw values are converted.
  A GET and POST handler sharing a route therefore declare separate schemas,
  so that a page can render with no parameters while its form submission requires them.
  Path parameters shared by several methods are declared in each fields class; this duplication is deliberate.

  An inner fields class must derive directly from `object`.
  Its namespace contains no framework names, so every annotated name in its body is a field,
  including names with leading underscores.

  Any public field annotation in the endpoint class body raises TypeError,
  because it is most likely a field mistakenly declared outside of a fields class.
  The fields object is not exposed as an attribute; handlers receive it precisely typed as their parameter.

  Subclasses must derive directly from Endpoint; defining an intermediate Endpoint subclass raises TypeError.

  Field types are type forms (PEP 747), so Literal, union and type alias type forms are accepted and enforced.
  A value outside of a required literal set is rejected.

  ## Optional and Multi-value Fields

  For each field, the outermost type form determines the HTTP parameter validation:
  * `T|None` marks the field as optional (None if the parameter is absent or an explicit JSON null);
  * `list[T]` marks it as multi-value, collecting every value submitted for its key (e.g. multi-select).
    A single NUL character submitted for the key in form data or query parameters is the empty list;
    pithy.js sends this for a set of valued checkboxes when none is checked, so that `list[T]` represents the checked subset.
    NUL mixed with other values is rejected. Empty strings remain list elements. JSON uses an explicit empty array.
  * `list[T]|None` is an optional multi-value field (None if the key is not submitted at all).

  ## Blank Values

  Path, query and form data are string sources: every value is a string, so they cannot represent None directly.
  An HTML form submits the empty string for an input with no value, e.g. an unset date or number input.
  Fields from these sources are therefore transtructed with `blank_to_none=True` (see `Transtructor`):
  the empty string becomes None for any type that has a None member, e.g. `start:datetime|None`.
  This includes `str|None`; declare plain `str` to receive empty strings.
  The rule applies to nested types as well, e.g. the elements of `list[int|None]`.
  JSON bodies can represent null, so the empty string is not converted; a JSON `""` for `datetime|None` is rejected.
  Custom converters receive the raw value unaltered from either kind of source.

  ## Unions

  For form data, all incoming fields are either raw strings or file uploads.
  Union types as supported by Transtructor are of limited value for string fields: `str|int` will always pass through the `str`.
  Unions are more generally applicable for JSON body fields.
  See `Transtructor` for the full details of union type conversion.

  ## Converters

  For each field, value conversion of raw request data is handled by either a per-class Transtructor or a per-field converter.
  The converter receives the whole field input and converts it to the full declared field type.
  For a multi-value field, a single submitted value is first wrapped into a one-element list,
  and the form/query NUL marker becomes the empty list, so the converter receives a list (or None from an explicit JSON null).

  To customize conversion for a specific field, define a `converters` dict in the endpoint class body as a class variable
  mapping field names to converter callables of the form `(raw) -> value`:
    class MyEndpoint(Endpoint):
      class Get:
        my_field:MyType
      def get(self, request:Request, fields:Get) -> Response: ...
      converters = dict(my_field=lambda raw: MyType.from_string(raw))
  A converter applies to the field of that name in every fields class that declares it; those fields must share one type.
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
  The body field must be declared in at least one fields class; it applies to every fields class that declares it.

  # Lifecycle

  All Endpoint classes take the following constructor parameters:
  * `request:Request`
  * `path_params:dict[str,object]`

  Request handling flow:
  * The server constructs the endpoint, which selects the handler and fields schema for the request method,
    creates its internal fields object and fills it from path and query params.
    Duplicates across path and query, excess params not corresponding to fields, and conversion failures raise BadRequestError,
    as does a body on a method that does not accept one.
  * If the client sent `Expect: 100-continue`, the server calls `handle_expect_100_continue`,
    which dispatches to the `expect_100_continue` hook with the fields object; by default this returns CONTINUE.
    At this stage body fields are not yet filled, so a subclass hook can reject a request from its path and query fields
    before the body is uploaded. Since the hook serves every handler, its `fields` parameter must be annotated as the union
    of the fields classes of all handlers defined, e.g. `fields:None|Post` when `get` declares no fields class.
  * The server calls `prepare`, which reads the body (if any), fills body fields, and performs final validation:
    duplicate params across sources, excess body params, missing required fields.
  * The server calls `handle_request`, which dispatches to the subclass handler for the request method.
  '''

  max_body_bytes:ClassVar[int] = 0 # Must be overridden by subclasses that expect body parameters; requires a body method handler.

  # Top-level customization: per-field-name converters, collected from the class body only. Signature: (raw) -> value.
  # A field-specific override may wrap its own Transtructor if the shared default is insufficient.
  converters:ClassVar[dict[str,Callable[[object],object]]] = {}

  body_field:ClassVar[str] = '' # If specified, the whole parsed request body fills the single field of this name.

  # Private per-subclass Transtructor, created lazily by the prefigure/selector classmethods.
  # Subclasses with no customizations leave this None and resolve against the shared default.
  _transtructor:ClassVar[Transtructor|None] = None

  # Set per-subclass once field converters have been resolved; customization is an error afterwards.
  _converters_resolved:ClassVar[bool] = False

  # Built by __init_subclass__ from the handler methods and inner fields classes, keyed by HTTP method.
  _specs:ClassVar[dict[str,_MethodSpec]]

  _fields_obj:object # The per-request fields instance; handlers receive it precisely typed as their `fields` parameter.
  _spec:_MethodSpec # The spec selected for the request method.
  _fields:dict[str,_FieldInfo] # The field infos of the selected spec.
  _fill_param_sources:dict[str,str]


  def __init_subclass__(cls, **kwargs:Any) -> None:
    super().__init_subclass__(**kwargs)

    for base in cls.__bases__:
      if issubclass(base, Endpoint) and base is not Endpoint:
        raise TypeError(
          f'{cls.__qualname__}: Endpoint subclasses must derive directly from Endpoint; {base.__qualname__} is an intermediate Endpoint subclass.')

    _check_obsolete_names(cls)

    cls_annotations = get_annotations(cls)
    for name, hint in cls_annotations.items():
      if name.startswith('_') or hint is ClassVar or get_origin(hint) is ClassVar: continue
      raise TypeError(
        f'{cls.__qualname__}.{name}: unexpected public annotation in Endpoint subclass body; '
        'declare request fields in an inner fields class named for the HTTP method, e.g. Get or Post.')

    # Converters are collected from their class bodies only; bases and mixins do not contribute.
    converters:dict[str,Callable[[object],object]] = cls.__dict__.get('converters', {})

    specs:dict[str,_MethodSpec] = {}
    for method, handler_name in handler_methods.items():
      class_name = method.capitalize()
      handler = cls.__dict__.get(handler_name)
      fields_class:type[Any] = cls.__dict__.get(class_name, NoneType) # NoneType() is None, the fields object of a handler without fields.
      if handler is None:
        if fields_class is not NoneType:
          raise TypeError(f'{cls.__qualname__}.{class_name} is declared but has no matching `{handler_name}` handler method.')
        continue
      if fields_class is not NoneType and (not isinstance(fields_class, type) or fields_class.__bases__ != (object,)):
        raise TypeError(f'{cls.__qualname__}.{class_name} must be a class deriving directly from object.')
      _validate_handler(cls, handler_name=handler_name, handler=handler, fields_classes=frozenset({fields_class}))
      fields:dict[str,_FieldInfo] = {}
      for name, hint in get_annotations(fields_class).items():
        if hint is ClassVar or get_origin(hint) is ClassVar: continue
        field_type, is_optional, is_list = _unwrap_field_type(hint)
        # Per-field converters bind now; transtructor-backed converters resolve lazily on the first request,
        # so that prefigure/selector customizations registered after the class body are honored.
        convert = converters.get(name)
        fields[name] = _FieldInfo(name=name, field_type=field_type, is_optional=is_optional, is_list=is_list,
          convert_str=convert, convert_typed=convert)
      specs[method] = _MethodSpec(method=method, handler_name=handler_name, fields_class=fields_class, fields=fields)

    if not specs:
      raise TypeError(f'{cls.__qualname__}: define at least one handler method: {", ".join(handler_methods.values())}.')
    cls._specs = specs

    if (expect_hook := cls.__dict__.get('expect_100_continue')) is not None:
      _validate_handler(cls, handler_name='expect_100_continue', handler=expect_hook,
        fields_classes=frozenset(spec.fields_class for spec in specs.values()))

    declared_names = {name for spec in specs.values() for name in spec.fields}
    if cls.body_field and cls.body_field not in declared_names:
      raise TypeError(f'{cls.__qualname__}: body_field {cls.body_field!r} does not name a declared field.')
    for name in converters:
      # A converter applies by name to every fields class declaring it, so those fields must share one type.
      typed = [(spec.fields_class.__name__, spec.fields[name].field_type) for spec in specs.values() if name in spec.fields]
      if not typed:
        raise TypeError(f'{cls.__qualname__}: converter {name!r} does not name a declared field.')
      if any(t != typed[0][1] for _, t in typed):
        desc = ', '.join(f'{c}.{name}:{t!r}' for c, t in typed)
        raise TypeError(f'{cls.__qualname__}: converter {name!r} applies to fields of differing types: {desc}.')

    methods = set(specs)
    if 'GET' in methods: methods.add('HEAD')
    cls._methods = frozenset(methods)

    if cls.max_body_bytes and not (methods & body_methods):
      raise TypeError(f'{cls.__qualname__}: max_body_bytes is set but no body method handler is defined: '
        f'{", ".join(handler_methods[m] for m in sorted(body_methods))}.')


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
    specs:dict[str,_MethodSpec] = {}
    for method, spec in cls._specs.items():
      fields:dict[str,_FieldInfo] = {}
      for name, field in spec.fields.items():
        if field.convert_str is None:
          # Security boundary: transtruct is only ever invoked on the declared field type, never on the Endpoint/handler type.
          # Do not "simplify" this into transtructing the whole endpoint.
          try:
            str_fn = transtructor.transtructor_for(field.field_type, blank_to_none=True)
            typed_fn = transtructor.transtructor_for(field.field_type)
          except (TypeError, TranstructorError) as e:
            raise TypeError(
              f'{cls.__qualname__}.{spec.fields_class.__name__}.{name}: no converter is available for field type {field.field_type!r}.') from e
          field = replace(field, convert_str=_transtruct_converter(str_fn), convert_typed=_transtruct_converter(typed_fn))
        fields[name] = field
      specs[method] = replace(spec, fields=fields)
    cls._specs = specs
    cls._converters_resolved = True


  def __init__(self, request:Request, path_params:Mapping[str,object]) -> None:
    '''
    Select the handler for the request method, then create the fields instance and fill it from path and query params.
    Body fields are filled later by `prepare`.
    Raises MethodNotAllowedError for an unhandled method, and BadRequestError for duplicate, excess, or unconvertible params.
    '''
    cls = type(self)
    if not cls._converters_resolved: cls._resolve_converters()
    method = request.method
    spec = cls._specs.get('GET' if method == 'HEAD' else method)
    if spec is None: raise MethodNotAllowedError(cls._methods)
    if method not in body_methods and (request.media_type or request.content_length or 'transfer-encoding' in request.headers):
      raise BadRequestError(f'{method} request must not carry a body.')
    self._spec = spec
    self._fields = spec.fields
    self._fields_obj = spec.fields_class()
    self._fill_param_sources = {}
    for name, raw in path_params.items():
      self._fill_param(name=name, raw=raw, source='path', is_str_source=True, accept_empty_list_marker=False)
    for name, vals in request.query_multi.items():
      # Match the shape of the form body parsers: a single value is a scalar, repeated values are a list.
      # A repeated key for a non-list field then fails conversion, just as it would in a form body.
      self._fill_param(name=name, raw=(vals if len(vals) > 1 else vals[0]), source='query',
        is_str_source=True, accept_empty_list_marker=True)

    if request.content_length is not None and request.content_length > self.max_body_bytes:
      # Reject a declared body that exceeds the declared max before it is read.
      raise BodyTooLargeError(length=request.content_length, max_bytes=self.max_body_bytes)


  def handle_expect_100_continue(self, request:Request) -> Response:
    'Framework method: dispatch the `Expect: 100-continue` header to the `expect_100_continue` hook with the fields object.'
    return self.expect_100_continue(request, self._fields_obj)


  def expect_100_continue(self, request:Request, fields:Any) -> Response:
    '''
    Handle the `Expect: 100-continue` header, given the fields object filled from path and query params.
    Those params have already been validated during construction, so by default this returns CONTINUE
    to allow the client to send the body. Subclasses may override this to reject the request before the body is read.
    '''
    return Response(status=HTTPStatus.CONTINUE)


  def prepare(self, request:Request) -> None:
    '''
    Fill body params and perform final validation.
    Raises BadRequestError on excess body params, duplicate params across sources, or missing required fields.
    '''
    if request.media_type:
      is_form = request.media_type in ('application/x-www-form-urlencoded', 'multipart/form-data')
      for name, raw in request.body_params(self.max_body_bytes, body_field=self.body_field).items():
        self._fill_param(name=name, raw=raw, source='body', is_str_source=is_form, accept_empty_list_marker=is_form)
    for name, field in self._fields.items():
      if hasattr(self._fields_obj, name): continue
      if not field.is_optional:
        raise BadRequestError(f'Missing required parameter: {name!r}.')
      setattr(self._fields_obj, name, None)


  def handle_request(self, request:Request) -> Response:
    'Dispatch to the handler method selected at construction; HEAD requests dispatch to `get`.'
    handler:Callable[[Request,Any],Response] = getattr(self, self._spec.handler_name)
    return handler(request, self._fields_obj)


  def get(self, request:Request, fields:Any) -> Response:
    'Handle a GET (or HEAD) request with its precisely typed fields object. Subclasses define this to accept GET.'
    raise NotImplementedError

  def post(self, request:Request, fields:Any) -> Response:
    'Handle a POST request with its precisely typed fields object. Subclasses define this to accept POST.'
    raise NotImplementedError

  def put(self, request:Request, fields:Any) -> Response:
    'Handle a PUT request with its precisely typed fields object. Subclasses define this to accept PUT.'
    raise NotImplementedError

  def patch(self, request:Request, fields:Any) -> Response:
    'Handle a PATCH request with its precisely typed fields object. Subclasses define this to accept PATCH.'
    raise NotImplementedError

  def delete(self, request:Request, fields:Any) -> Response:
    'Handle a DELETE request with its precisely typed fields object. Subclasses define this to accept DELETE.'
    raise NotImplementedError


  def _fill_param(self, name:str, raw:object, source:str, *, is_str_source:bool, accept_empty_list_marker:bool) -> None:
    '''
    Convert and set a single field. `is_str_source` is True for path, query and form data, where every value is a string.
    Such sources transtruct with `blank_to_none=True`.
    `accept_empty_list_marker` is True for query and form data, where a lone NUL value denotes the empty list.
    '''
    if prev := self._fill_param_sources.get(name):
      raise BadRequestError(f'Duplicate parameter {name!r} in {prev} and {source}.')
    field = self._fields.get(name)
    if field is None:
      raise BadRequestError(f'Unknown parameter {name!r} in {source}.')
    self._fill_param_sources[name] = source
    convert = field.convert_str if is_str_source else field.convert_typed
    assert convert is not None # Resolved by _resolve_converters at construction.
    if field.is_list and raw is not None:
      # A single submitted value fills a multi-value field as a one-element list.
      # This normalization must precede conversion: transtruct would iterate a bare str into its characters.
      # None (an explicit JSON null) is preserved for the field type union to accept or reject.
      raw = raw if isinstance(raw, list) else [raw]
      if accept_empty_list_marker and '\x00' in raw:
        if len(raw) != 1:
          raise BadRequestError(f'Empty-list NUL marker mixed with other values for parameter {name!r}.')
        raw = []
    try: converted_value = convert(raw)
    except (ValueError, TypeError, TranstructorError) as e:
      # Truncate the raw value so that a large or whole-body value is not reflected back in the error response.
      raise BadRequestError(f'Invalid value for parameter {name!r}: {repr(raw)[:64]}.') from e
    # Validate outside of the try clause above, so that a converter returning a mistyped value raises TypeError (500).
    setattr(self._fields_obj, name, req_type(converted_value, field.field_type))


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


def _check_obsolete_names(cls:type[Endpoint]) -> None:
  'Raise TypeError for class body names from the single-schema Endpoint design, or that would otherwise mislead.'
  d = cls.__dict__
  if 'handle_request' in d:
    raise TypeError(f'{cls.__qualname__}: define per-method handlers such as `get` or `post`, not framework method `handle_request`.')
  if 'handle_expect_100_continue' in d:
    raise TypeError(f'{cls.__qualname__}: override `expect_100_continue`, not framework method `handle_expect_100_continue`.')
  if 'handle_endpoint' in d:
    raise TypeError(f'{cls.__qualname__}: `handle_endpoint` is obsolete; define per-method handlers such as `get` or `post`.')
  if 'Fields' in d:
    raise TypeError(f'{cls.__qualname__}.Fields is obsolete; name the inner fields class for its HTTP method, e.g. Get or Post.')
  if 'methods' in d:
    raise TypeError(f'{cls.__qualname__}.methods is obsolete; accepted methods are derived from the handler methods defined.')
  for name in _reserved_method_names:
    if name in d:
      raise TypeError(f'{cls.__qualname__}.{name}: {name.upper()} requests are not dispatched to handler methods.')


def _validate_handler(cls:type[Endpoint], *, handler_name:str, handler:object, fields_classes:frozenset[type[Any]]) -> None:
  '''
  Validate a concrete Endpoint subclass handler method at class definition time.
  The `fields` parameter must be annotated as exactly the members of `fields_classes`: a single class or their union.
  NoneType in `fields_classes` corresponds to a `None` annotation, for a handler without a fields class.
  '''
  qualname = f'{cls.__qualname__}.{handler_name}'
  if not callable(handler):
    raise TypeError(f'{qualname} must be a method.')
  params = tuple(signature(handler, annotation_format=Format.STRING).parameters.values())
  if len(params) != 3 or any(p.kind is not Parameter.POSITIONAL_OR_KEYWORD for p in params):
    raise TypeError(f'{qualname} must have signature `(self, request, fields)`.')
  if tuple(p.name for p in params) != ('self', 'request', 'fields'):
    raise TypeError(f'{qualname} parameter names must be `(self, request, fields)`.')
  if any(p.default is not Parameter.empty for p in params):
    raise TypeError(f'{qualname} parameters must not have defaults.')
  annotations = _handler_annotations(qualname, handler)
  fields_hint = annotations.get('fields', Default._)
  if fields_hint is Default._:
    raise TypeError(f'{qualname}.fields must be annotated.')
  fields_hint = normalize_type_form(fields_hint)
  declared = frozenset(get_args(fields_hint) if get_origin(fields_hint) is Union else (fields_hint,))
  if declared != fields_classes:
    names = ' | '.join(sorted('None' if c is NoneType else c.__qualname__ for c in fields_classes))
    raise TypeError(f'{qualname}.fields must be annotated as {names}.')


def _handler_annotations(qualname:str, handler:Callable[...,Any]) -> dict[str,Any]:
  'Evaluate the annotations of a handler method or function, checking the `request` and return annotations.'
  try: annotations = get_annotations(handler)
  except (NameError, TypeError) as e:
    raise TypeError(f'{qualname} annotations could not be evaluated: {e}') from e
  if annotations.get('request') is not Request:
    raise TypeError(f'{qualname}.request must be annotated as Request.')
  response_type = annotations.get('return')
  if not isinstance(response_type, type) or not issubclass(response_type, Response):
    raise TypeError(f'{qualname} return must be annotated as Response or a Response subclass.')
  return annotations
