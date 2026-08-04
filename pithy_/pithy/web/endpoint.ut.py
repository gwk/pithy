# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from http import HTTPStatus
from types import NoneType
from typing import Annotated, Any, Literal, TypeVar
from urllib.parse import urlencode

from pithy.transtruct import Transtructor
from pithy.web.endpoint import _unwrap_field_type, Endpoint
from pithy.web.errors import MethodNotAllowedError, ResponseError
from pithy.web.request import Request, UploadedFile
from pithy.web.requestconn import BodyTooLargeError, BytesConn
from pithy.web.response import Response
from pithy.web.router import Router
from typing_extensions import TypeForm  # TODO: import from typing once we require Python 3.15.
from utest import utest, utest_exc, utest_run, utest_val


def _make_request(query:dict[str,str|int|list[str]]|None=None, *, media_type:str='', body:bytes=b'') -> Request:
  query_str = urlencode(query, doseq=True) if query else '' # doseq expands list values into repeated keys.
  headers:dict[str,str] = {}
  if media_type:
    headers['content-type'] = media_type
  content_length = len(body) if body else None
  conn = BytesConn(body) if media_type else None
  return Request(method='GET', scheme='http', host='localhost', port=80, path='/', query_str=query_str, headers=headers,
    client_addr=('127.0.0.1', 0), content_length=content_length, conn=conn)


# _unwrap_field_type: analyze into (field_type, is_optional, is_list).
utest((int, False, False), _unwrap_field_type, int)
utest((int|None, True, False), _unwrap_field_type, int|None)
utest((list[int], False, True), _unwrap_field_type, list[int])
utest((list[int]|None, True, True), _unwrap_field_type, list[int]|None)
utest((str|None, True, False), _unwrap_field_type, str|None)

# Literal, Annotated and alias type forms are decomposed like any other type form.
type _Ids = list[int]
type _OptName = str|None

utest((Literal['a','b'], False, False), _unwrap_field_type, Literal['a','b'])
utest((Literal['a','b']|None, True, False), _unwrap_field_type, Literal['a','b']|None)
utest((list[Literal['a','b']], False, True), _unwrap_field_type, list[Literal['a','b']])
utest((list[Literal['a','b']]|None, True, True), _unwrap_field_type, list[Literal['a','b']]|None)
utest((int, False, False), _unwrap_field_type, Annotated[int,'meta'])
utest((list[int], False, True), _unwrap_field_type, Annotated[list[int],'meta'])
utest((list[int], False, True), _unwrap_field_type, _Ids)
# The alias union member is not expanded by top-level normalization; is_a normalizes members recursively during validation.
utest((_Ids|None, True, True), _unwrap_field_type, _Ids|None)
utest((str|None, True, False), _unwrap_field_type, _OptName)
utest((NoneType, False, False), _unwrap_field_type, None)

# A union field type is converted as a whole; only the outer type form sets the optional and list flags.
utest((int|str, False, False), _unwrap_field_type, int|str)
utest((int|str|None, True, False), _unwrap_field_type, int|str|None)
utest((list[int]|int, False, False), _unwrap_field_type, list[int]|int)
# Accepted here even though the transtructor will require a selector for it when converters are resolved.
utest((list[int]|list[str], False, False), _unwrap_field_type, list[int]|list[str])

# Rejected type forms.
utest_exc(TypeError, _unwrap_field_type, list[int,str]) # type: ignore[misc] # Unsupported multi-parameter list (invalid statically).
utest_exc(TypeError, _unwrap_field_type, Callable[[int],int]) # Callables would pass the raw request value through unconverted.
utest_exc(TypeError, _unwrap_field_type, type[int]) # Likewise; the origin of `type[T]` is callable.
utest_exc(TypeError, _unwrap_field_type, TypeVar('T')) # Not a constructible type form.


# Basic field types.

class IntEndpoint(Endpoint):
  max_body_bytes = 1024
  class Fields:
    id:int
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.id}')


class MultiFieldEndpoint(Endpoint):
  class Fields:
    name:str
    count:int
    ratio:float
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.name},{self.fields.count},{self.fields.ratio}')


class OptionalEndpoint(Endpoint):
  class Fields:
    name:str
    tag:str|None
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.name},{self.fields.tag}')


class DateEndpoint(Endpoint):
  class Fields:
    d:date
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.d}')


class DatetimeEndpoint(Endpoint):
  class Fields:
    dt:datetime
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.dt}')


class TimeEndpoint(Endpoint):
  class Fields:
    t:time
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.t}')


class BoolEndpoint(Endpoint):
  max_body_bytes = 1024
  class Fields:
    flag:bool
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.flag}')


def endpoint_fields(cls:type[Endpoint], **kwargs:str) -> dict[str,Any]:
  'Construct an endpoint with path params, prepare it, and return the populated field values.'
  request = _make_request()
  ep = cls(request=request, path_params=kwargs)
  ep.prepare(request)
  return {k: getattr(ep.fields, k) for k in ep._fields}


# Field parsing from path params (string conversion).
utest(dict(id=42), endpoint_fields, IntEndpoint, id='42')
utest(dict(name='alice', count=3, ratio=1.5), endpoint_fields, MultiFieldEndpoint, name='alice', count='3', ratio='1.5')
utest(dict(name='alice', tag='admin'), endpoint_fields, OptionalEndpoint, name='alice', tag='admin')
utest(dict(name='alice', tag=None), endpoint_fields, OptionalEndpoint, name='alice')
utest(dict(d=date(2026, 3, 14)), endpoint_fields, DateEndpoint, d='2026-03-14')
utest(dict(dt=datetime(2026, 3, 14, 12, 0)), endpoint_fields, DatetimeEndpoint, dt='2026-03-14T12:00:00')
utest(dict(t=time(12, 30)), endpoint_fields, TimeEndpoint, t='12:30:00')

# Error cases.
utest_exc(ResponseError, endpoint_fields, IntEndpoint) # Missing required param.
utest_exc(ResponseError, endpoint_fields, IntEndpoint, id='abc') # Bad conversion at construction.
utest_exc(ResponseError, endpoint_fields, IntEndpoint, id='5', extra='ignored') # Excess path param.

# Bool field from various strings.
@utest_run
def _() -> None:
  for s in ('true', '1', 'yes'):
    ep = BoolEndpoint(_make_request(), path_params=dict(flag=s))
    utest_val(True, ep.fields.flag, desc=f'bool from {s!r}')
  for s in ('false', '0', 'no', ''):
    ep = BoolEndpoint(_make_request(), path_params=dict(flag=s))
    utest_val(False, ep.fields.flag, desc=f'bool from {s!r}')


# Invalid bool string raises BadRequestError (inherited from the tightened transtruct_bool).
utest_exc(ResponseError, BoolEndpoint, _make_request(), dict(flag='maybe'))


# Underscore-prefixed names are ordinary fields within the Fields namespace.

class UnderscoreFieldEndpoint(Endpoint):
  class Fields:
    name:str
    _debug:bool|None
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.name},{self.fields._debug}')


utest(dict(name='a', _debug=True), endpoint_fields, UnderscoreFieldEndpoint, name='a', _debug='1')
utest(dict(name='a', _debug=None), endpoint_fields, UnderscoreFieldEndpoint, name='a')


# Custom per-field-name converters.

class Color(Enum):
  red = 'red'
  green = 'green'
  blue = 'blue'


class CustomConverterEndpoint(Endpoint):
  converters = {'color': lambda raw: Color(raw)}
  class Fields:
    color:Color
  fields:Fields

  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.color.value}')


utest(dict(color=Color.red), endpoint_fields, CustomConverterEndpoint, color='red')
utest_exc(ResponseError, CustomConverterEndpoint, _make_request(), dict(color='purple'))


# A converter for a multi-value field receives the whole normalized list, so it can control the list shape.

def _dedupe_tags(raw:Any) -> list[str]:
  return sorted({str(el) for el in raw})


class ListConverterEndpoint(Endpoint):
  max_body_bytes = 1024
  converters = {'tags': _dedupe_tags}
  class Fields:
    tags:list[str]
  fields:Fields

  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.tags}')


# Direct subclassing is enforced: intermediate Endpoint subclasses raise TypeError.

def _make_sub_subclass() -> type[Endpoint]:
  class SubIntEndpoint(IntEndpoint):
    pass
  return SubIntEndpoint

utest_exc(TypeError, _make_sub_subclass)


# Public annotations belong in the inner Fields class; a stray field annotation on the endpoint body raises TypeError.

def _make_stray_annotation_endpoint() -> type[Endpoint]:
  class StrayAnnotationEndpoint(Endpoint):
    name:str
  return StrayAnnotationEndpoint

utest_exc(TypeError, _make_stray_annotation_endpoint)


# The inner Fields class must derive directly from object.

class _FieldsBase:
  x:int

def _make_derived_fields_endpoint() -> type[Endpoint]:
  class DerivedFieldsEndpoint(Endpoint):
    class Fields(_FieldsBase):
      y:int
    fields:Fields
  return DerivedFieldsEndpoint

utest_exc(TypeError, _make_derived_fields_endpoint)


# Declaring an inner Fields class requires the `fields:Fields` annotation for type checker precision.

def _make_unannotated_fields_endpoint() -> type[Endpoint]:
  class UnannotatedFieldsEndpoint(Endpoint):
    class Fields:
      x:int
  return UnannotatedFieldsEndpoint

utest_exc(TypeError, _make_unannotated_fields_endpoint)


# A `fields` annotation without an inner Fields class raises TypeError.

def _make_fields_annotation_only_endpoint() -> type[Endpoint]:
  class FieldsAnnotationOnlyEndpoint(Endpoint):
    fields:int
  return FieldsAnnotationOnlyEndpoint

utest_exc(TypeError, _make_fields_annotation_only_endpoint)


# Shared converters are composed as plain dicts in the class body; there is no converter inheritance.

color_converters:dict[str,Callable[[object],object]] = {'color': lambda raw: Color(raw)}

class ComposedConverterEndpoint(Endpoint):
  converters = color_converters | {'name': lambda raw: str(raw).upper()}
  class Fields:
    color:Color
    name:str
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.color.value},{self.fields.name}')


utest(dict(color=Color.green, name='TEST'), endpoint_fields, ComposedConverterEndpoint, color='green', name='test')


# No-field endpoint: the inner Fields class is optional.

class NoFieldEndpoint(Endpoint):
  def handle_request(self, request:Request) -> Response:
    return Response(body='ok')


@utest_run
def _() -> None:
  'Endpoint: no fields.'
  req = _make_request()
  ep = NoFieldEndpoint(req, path_params={})
  ep.prepare(req)
  response = ep.handle_request(req)
  utest_val(b'ok', response.body)


# prepare fills fields and handle_request returns the response.

@utest_run
def _() -> None:
  'Endpoint: prepare with query params.'
  req = _make_request(query=dict(tag='admin'))
  ep = OptionalEndpoint(req, path_params=dict(name='alice'))
  ep.prepare(req)
  response = ep.handle_request(req)
  utest_val(b'alice,admin', response.body)


# handle_expect_100_continue returns CONTINUE; validation already happened at construction.

@utest_run
def _() -> None:
  'Endpoint: handle_expect_100_continue returns CONTINUE.'
  req = _make_request(query=dict(id='42'))
  ep = IntEndpoint(req, path_params={})
  response = ep.handle_expect_100_continue(req)
  utest_val(HTTPStatus.CONTINUE, response.status)


@utest_run
def _() -> None:
  'Endpoint: construction raises on duplicate path/query params.'
  req = _make_request(query=dict(id='42'))
  utest_exc(ResponseError, IntEndpoint, req, dict(id=5))


@utest_run
def _() -> None:
  'Endpoint: construction raises on excess query params.'
  req = _make_request(query=dict(unknown='x'))
  utest_exc(ResponseError, IntEndpoint, req, dict(id='1'))


# Body-filling endpoint (declares max_body_bytes).

class BodyEndpoint(Endpoint):
  max_body_bytes = 1024
  class Fields:
    name:str
    tag:str|None
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.name},{self.fields.tag}')

class ListEndpoint(Endpoint):
  max_body_bytes = 1024
  class Fields:
    tags:list[str]
    counts:list[int]
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.tags},{self.fields.counts}')


@utest_run
def _() -> None:
  'Endpoint: prepare fills fields from body params.'
  req = _make_request(media_type='application/json', body=b'{"name":"alice","tag":"admin"}')
  ep = BodyEndpoint(req, path_params={})
  ep.prepare(req)
  response = ep.handle_request(req)
  utest_val(b'alice,admin', response.body)


@utest_run
def _() -> None:
  'Endpoint: prepare detects duplicate query/body params.'
  req = _make_request(query=dict(tag='query'), media_type='application/json', body=b'{"tag":"body"}')
  ep = BodyEndpoint(req, path_params=dict(name='alice'))
  expect = ep.handle_expect_100_continue(req)
  utest_val(HTTPStatus.CONTINUE, expect.status)
  utest_exc(ResponseError, ep.prepare, req)


@utest_run
def _() -> None:
  'Endpoint: prepare raises on excess body params.'
  req = _make_request(media_type='application/json', body=b'{"name":"alice","extra":"x"}')
  ep = BodyEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


@utest_run
def _() -> None:
  'Endpoint: prepare raises on missing required field with no body.'
  req = _make_request()
  ep = BodyEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


# JSON body with non-string value types.

@utest_run
def _() -> None:
  'Endpoint: prepare fills int field from JSON body with integer value.'
  req = _make_request(media_type='application/json', body=b'{"id":3}')
  ep = IntEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(3, ep.fields.id)


@utest_run
def _() -> None:
  'Endpoint: str field rejects JSON integer value.'
  req = _make_request(media_type='application/json', body=b'{"name":123}')
  ep = BodyEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


@utest_run
def _() -> None:
  'Endpoint: prepare fills list fields from JSON body with array values.'
  req = _make_request(media_type='application/json', body=b'{"tags":["a","b"],"counts":[1,2]}')
  ep = ListEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(['a', 'b'], ep.fields.tags)
  utest_val([1, 2], ep.fields.counts)


@utest_run
def _() -> None:
  'Endpoint: JSON null fills an optional field with None.'
  req = _make_request(media_type='application/json', body=b'{"name":"alice","tag":null}')
  ep = BodyEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(None, ep.fields.tag)


@utest_run
def _() -> None:
  'Endpoint: JSON null for a required field raises BadRequestError.'
  req = _make_request(media_type='application/json', body=b'{"id":null}')
  ep = IntEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


@utest_run
def _() -> None:
  'Endpoint: a single JSON scalar fills a list field as a one-element list.'
  req = _make_request(media_type='application/json', body=b'{"tags":"a","counts":1}')
  ep = ListEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(['a'], ep.fields.tags)
  utest_val([1], ep.fields.counts)


@utest_run
def _() -> None:
  'Endpoint: bool field filled from JSON true value.'
  req = _make_request(media_type='application/json', body=b'{"flag":true}')
  ep = BoolEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(True, ep.fields.flag)


@utest_run
def _() -> None:
  'Endpoint: malformed JSON body raises BadRequestError.'
  req = _make_request(media_type='application/json', body=b'{not json')
  ep = BodyEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


# Nested dataclass fields.

@dataclass
class Point:
  x:int
  y:int


class NestedEndpoint(Endpoint):
  max_body_bytes = 1024
  class Fields:
    point:Point
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.point}')


class NestedListEndpoint(Endpoint):
  max_body_bytes = 1024
  class Fields:
    points:list[Point]
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.points}')


@utest_run
def _() -> None:
  'Endpoint: nested dataclass field filled from JSON body.'
  req = _make_request(media_type='application/json', body=b'{"point":{"x":1,"y":2}}')
  ep = NestedEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(Point(1, 2), ep.fields.point)


@utest_run
def _() -> None:
  'Endpoint: list[dataclass] field filled from JSON body.'
  req = _make_request(media_type='application/json', body=b'{"points":[{"x":1,"y":2},{"x":3,"y":4}]}')
  ep = NestedListEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val([Point(1, 2), Point(3, 4)], ep.fields.points)


# List fields.



class OptionalListEndpoint(Endpoint):
  max_body_bytes = 1024
  class Fields:
    tags:list[str]|None
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.tags}')


def _urlencoded_request(body:str) -> Request:
  return _make_request(media_type='application/x-www-form-urlencoded', body=body.encode())


def _multipart_request(boundary:str, *parts:bytes) -> Request:
  b = boundary.encode()
  body = b''
  for part in parts:
    body += b'--' + b + b'\r\n' + part + b'\r\n'
  body += b'--' + b + b'--\r\n'
  return _make_request(media_type=f'multipart/form-data; boundary={boundary}', body=body)


def endpoint_body_fields(cls:type[Endpoint], body:str) -> dict[str,Any]:
  'Construct an endpoint with a urlencoded body, prepare it, and return the populated field values.'
  req = _urlencoded_request(body)
  ep = cls(req, path_params={})
  ep.prepare(req)
  return {k: getattr(ep.fields, k) for k in ep._fields}


@utest_run
def _() -> None:
  'Endpoint: list[str] field filled from urlencoded body with multiple values.'
  result = endpoint_body_fields(ListEndpoint, 'tags=a&tags=b&tags=c&counts=1&counts=2')
  utest_val(['a', 'b', 'c'], result['tags'])
  utest_val([1, 2], result['counts'])


@utest_run
def _() -> None:
  'Endpoint: a multi-value field converter receives the whole list; a single value arrives as a one-element list.'
  utest_val(dict(tags=['a', 'b']), endpoint_body_fields(ListConverterEndpoint, 'tags=b&tags=a&tags=b'))
  utest_val(dict(tags=['x']), endpoint_body_fields(ListConverterEndpoint, 'tags=x'))


@utest_run
def _() -> None:
  'Endpoint: list fields filled from repeated query keys.'
  req = _make_request(query=dict(tags=['a', 'b'], counts=['1', '2']))
  ep = ListEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(['a', 'b'], ep.fields.tags)
  utest_val([1, 2], ep.fields.counts)


@utest_run
def _() -> None:
  'Endpoint: a single query value fills a list field as a one-element list.'
  req = _make_request(query=dict(tags='a', counts='1'))
  ep = ListEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(['a'], ep.fields.tags)
  utest_val([1], ep.fields.counts)


@utest_run
def _() -> None:
  'Endpoint: a repeated query key for a non-list field raises BadRequestError.'
  utest_exc(ResponseError, IntEndpoint, _make_request(query=dict(id=['1', '2'])), {})


@utest_run
def _() -> None:
  'Endpoint: list[str]|None field with values present.'
  result = endpoint_body_fields(OptionalListEndpoint, 'tags=x&tags=y')
  utest_val(['x', 'y'], result['tags'])


@utest_run
def _() -> None:
  'Endpoint: list[str]|None field absent from body is None.'
  result = endpoint_body_fields(OptionalListEndpoint, '')
  utest_val(None, result['tags'])


@utest_run
def _() -> None:
  'Endpoint: JSON null for an optional list field is None; the null is not wrapped into a list.'
  req = _make_request(media_type='application/json', body=b'{"tags":null}')
  ep = OptionalListEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(None, ep.fields.tags)


@utest_run
def _() -> None:
  'Endpoint: list[str] required but not submitted raises BadRequestError.'
  req = _urlencoded_request('')
  ep = ListEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


@utest_run
def _() -> None:
  'Endpoint: list field same name from query and body raises BadRequestError.'
  req = _make_request(query=dict(tags='a'), media_type='application/x-www-form-urlencoded', body=b'tags=b&counts=1')
  ep = ListEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


@utest_run
def _() -> None:
  'Endpoint: scalar field receiving multiple values raises BadRequestError.'
  req = _urlencoded_request('name=a&name=b')
  ep = BodyEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


# UploadedFile fields.

class UploadedFileEndpoint(Endpoint):
  max_body_bytes = 4096
  class Fields:
    file:UploadedFile
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.file.filename}')


@utest_run
def _() -> None:
  'Endpoint: UploadedFile field filled from multipart body.'
  part = b'Content-Disposition: form-data; name="file"; filename="hello.txt"\r\nContent-Type: application/octet-stream\r\n\r\nhello'
  req = _multipart_request('boundary123', part)
  ep = UploadedFileEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val('hello.txt', ep.fields.file.filename)
  utest_val(b'hello', ep.fields.file.data)


@utest_run
def _() -> None:
  'Endpoint: UploadedFile field raises BadRequestError when given a string value.'
  req = _urlencoded_request('file=not-a-file')
  ep = UploadedFileEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


@utest_run
def _() -> None:
  'Endpoint: UploadedFile field rejects a JSON dict with matching keys (prefigure guard).'
  body = b'{"file":{"field_name":"file","filename":"x.txt","data":"hi","content_type":"text/plain"}}'
  req = _make_request(media_type='application/json', body=body)
  ep = UploadedFileEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


class MultiFileEndpoint(Endpoint):
  max_body_bytes = 8192
  class Fields:
    files:list[UploadedFile]
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.files}')


@utest_run
def _() -> None:
  'Endpoint: list[UploadedFile] field filled from multiple multipart file parts.'
  part_a = b'Content-Disposition: form-data; name="files"; filename="a.txt"\r\nContent-Type: text/plain\r\n\r\nAAA'
  part_b = b'Content-Disposition: form-data; name="files"; filename="b.txt"\r\nContent-Type: text/plain\r\n\r\nBBB'
  req = _multipart_request('boundary123', part_a, part_b)
  ep = MultiFileEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(['a.txt', 'b.txt'], [f.filename for f in ep.fields.files])
  utest_val([b'AAA', b'BBB'], [f.data for f in ep.fields.files])


class MixedMultipartEndpoint(Endpoint):
  max_body_bytes = 8192
  class Fields:
    note:str
    file:UploadedFile
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.note}:{self.fields.file.filename}')


@utest_run
def _() -> None:
  'Endpoint: multipart body fills both text and file fields.'
  text_part = b'Content-Disposition: form-data; name="note"\r\n\r\nhello'
  file_part = b'Content-Disposition: form-data; name="file"; filename="f.bin"\r\nContent-Type: application/octet-stream\r\n\r\n\x00\x01'
  req = _multipart_request('boundary123', text_part, file_part)
  ep = MixedMultipartEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val('hello', ep.fields.note)
  utest_val('f.bin', ep.fields.file.filename)
  utest_val(b'\x00\x01', ep.fields.file.data)


# body_field mode: the whole parsed body fills a single named field.

class ListBodyFieldEndpoint(Endpoint):
  max_body_bytes = 1024
  body_field = 'payload'
  class Fields:
    payload:list[int]
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.payload}')


class IntBodyFieldEndpoint(Endpoint):
  max_body_bytes = 1024
  body_field = 'payload'
  class Fields:
    payload:int
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.payload}')


class PointBodyFieldEndpoint(Endpoint):
  max_body_bytes = 1024
  body_field = 'payload'
  class Fields:
    payload:Point
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.payload}')


@utest_run
def _() -> None:
  'Endpoint: body_field fills a list field from a JSON array body.'
  req = _make_request(media_type='application/json', body=b'[1,2,3]')
  ep = ListBodyFieldEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val([1, 2, 3], ep.fields.payload)


@utest_run
def _() -> None:
  'Endpoint: body_field fills a scalar field from a JSON scalar body.'
  req = _make_request(media_type='application/json', body=b'42')
  ep = IntBodyFieldEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(42, ep.fields.payload)


@utest_run
def _() -> None:
  'Endpoint: body_field fills a dataclass field from a JSON object body.'
  req = _make_request(media_type='application/json', body=b'{"x":1,"y":2}')
  ep = PointBodyFieldEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(Point(1, 2), ep.fields.payload)


@utest_run
def _() -> None:
  'Endpoint: body_field fills a dataclass field from a urlencoded body.'
  req = _urlencoded_request('x=1&y=2')
  ep = PointBodyFieldEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(Point(1, 2), ep.fields.payload)


class MixedBodyFieldEndpoint(Endpoint):
  max_body_bytes = 1024
  body_field = 'payload'
  class Fields:
    payload:Point
    label:str
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.label}:{self.fields.payload}')


@utest_run
def _() -> None:
  'Endpoint: body_field endpoint still fills other fields from query params.'
  req = _make_request(query=dict(label='a'), media_type='application/json', body=b'{"x":1,"y":2}')
  ep = MixedBodyFieldEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val('a', ep.fields.label)
  utest_val(Point(1, 2), ep.fields.payload)


@utest_run
def _() -> None:
  'Endpoint: query param sharing the body_field name raises duplicate error at prepare.'
  req = _make_request(query=dict(payload='1'), media_type='application/json', body=b'2')
  ep = IntBodyFieldEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


def _make_bad_body_field_endpoint() -> type[Endpoint]:
  class BadBodyFieldEndpoint(Endpoint):
    body_field = 'payload'
    class Fields:
      other:int
    fields:Fields
    def handle_request(self, request:Request) -> Response:
      return Response(body='')
  return BadBodyFieldEndpoint


# Class definition raises when body_field does not name a declared field.
utest_exc(TypeError, _make_bad_body_field_endpoint)


# body_field with an annotation-only payload class: transtruct instantiates it bare and sets attributes directly.

class BarePayload:
  x:int
  y:int
  note:str = 'default'


class BarePayloadEndpoint(Endpoint):
  max_body_bytes = 1024
  body_field = 'payload'
  class Fields:
    payload:BarePayload
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.payload}')


@utest_run
def _() -> None:
  'Endpoint: body_field fills an annotation-only payload class from a JSON object body.'
  req = _make_request(media_type='application/json', body=b'{"x":1,"y":2}')
  ep = BarePayloadEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(1, ep.fields.payload.x)
  utest_val(2, ep.fields.payload.y)
  utest_val('default', ep.fields.payload.note)


@utest_run
def _() -> None:
  'Endpoint: annotation-only payload missing a required key raises BadRequestError.'
  req = _make_request(media_type='application/json', body=b'{"x":1}')
  ep = BarePayloadEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


# body_field with a custom Transtructor: a selector chooses a concrete subtype from the top-level body.
# This is the motivating case for body_field: custom interpretation of the whole body as one object.

@dataclass
class Shape:
  kind:str


@dataclass
class Circle(Shape):
  radius:int


@dataclass
class Rect(Shape):
  w:int
  h:int


shape_transtructor = Transtructor(strict=False)

@shape_transtructor.selector(Shape)
def _select_shape(static_type:TypeForm[Any], val:Any, ctx:Any) -> TypeForm[Any]:
  match val:
    case {'kind': 'circle'}: return Circle
    case {'kind': 'rect'}: return Rect
    case _: return static_type


class ShapeBodyEndpoint(Endpoint):
  max_body_bytes = 1024
  body_field = 'shape'
  converters = {'shape': lambda raw: shape_transtructor.transtruct(Shape, raw)}
  class Fields:
    shape:Shape
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.shape}')


@utest_run
def _() -> None:
  'Endpoint: body_field with a selector Transtructor constructs the concrete subtype.'
  req = _make_request(media_type='application/json', body=b'{"kind":"circle","radius":3}')
  ep = ShapeBodyEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(Circle(kind='circle', radius=3), ep.fields.shape)


@utest_run
def _() -> None:
  'Endpoint: body_field with a selector Transtructor constructs an alternate subtype.'
  req = _make_request(media_type='application/json', body=b'{"kind":"rect","w":2,"h":3}')
  ep = ShapeBodyEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(Rect(kind='rect', w=2, h=3), ep.fields.shape)


# Per-class transtructor customization via the prefigure/selector classmethod decorators.

class PrefiguredPointEndpoint(Endpoint):
  max_body_bytes = 1024
  class Fields:
    point:Point
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.point}')


@PrefiguredPointEndpoint.prefigure(Point)
def _prefigure_point(cls:TypeForm[Any], val:Any, ctx:Any) -> Any:
  if isinstance(val, str):
    x, _, y = val.partition(',')
    return {'x': x, 'y': y}
  return val


@utest_run
def _() -> None:
  'Endpoint: per-class prefigure reshapes a string into a Point.'
  req = _make_request(media_type='application/json', body=b'{"point":"3,4"}')
  ep = PrefiguredPointEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(Point(3, 4), ep.fields.point)


@utest_run
def _() -> None:
  'Endpoint: per-class prefigure does not affect other endpoints using the same type.'
  req = _make_request(media_type='application/json', body=b'{"point":"3,4"}')
  ep = NestedEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


class ShapeSelectorEndpoint(Endpoint):
  max_body_bytes = 1024
  body_field = 'shape'
  class Fields:
    shape:Shape
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.shape}')


@ShapeSelectorEndpoint.selector(Shape)
def _select_shape_for_endpoint(static_type:TypeForm[Any], val:Any, ctx:Any) -> TypeForm[Any]:
  match val:
    case {'kind': 'circle'}: return Circle
    case {'kind': 'rect'}: return Rect
    case _: return static_type


@utest_run
def _() -> None:
  'Endpoint: per-class selector constructs the concrete subtype from the body.'
  req = _make_request(media_type='application/json', body=b'{"kind":"rect","w":4,"h":5}')
  ep = ShapeSelectorEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(Rect(kind='rect', w=4, h=5), ep.fields.shape)


# Literal and alias field types: the field holds the precise type, so handlers need no cast.

type Order = Literal['asc','desc']


class LiteralEndpoint(Endpoint):
  class Fields:
    order:Order
    rank:Literal[1,2]
    tag:Literal['a','b']|None
    counts:Annotated[list[int],'meta']
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    order:Order = self.fields.order # Statically precise; no cast required.
    return Response(body=f'{order},{self.fields.rank},{self.fields.tag},{self.fields.counts}')


utest(dict(order='asc', rank=1, tag='a', counts=[3]), endpoint_fields, LiteralEndpoint,
  order='asc', rank='1', tag='a', counts='3') # Note: rank is coerced from the raw string to the int literal member.
utest(dict(order='desc', rank=2, tag=None, counts=[3]), endpoint_fields, LiteralEndpoint,
  order='desc', rank='2', counts='3')

utest_exc(ResponseError, endpoint_fields, LiteralEndpoint, order='sideways', rank='1', counts='3') # Not a literal member.
utest_exc(ResponseError, endpoint_fields, LiteralEndpoint, order='asc', rank='3', counts='3')
utest_exc(ResponseError, endpoint_fields, LiteralEndpoint, order='asc', rank='1', tag='c', counts='3')


class LiteralListEndpoint(Endpoint):
  max_body_bytes = 1024
  class Fields:
    kinds:list[Literal['a','b']]
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.kinds}')


@utest_run
def _() -> None:
  'Endpoint: list of literals filled from a urlencoded body with multiple values.'
  body = urlencode([('kinds','a'), ('kinds','b')]).encode()
  req = _make_request(media_type='application/x-www-form-urlencoded', body=body)
  ep = LiteralListEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(['a', 'b'], ep.fields.kinds)


@utest_run
def _() -> None:
  'Endpoint: an invalid literal element of a list field raises BadRequestError.'
  body = urlencode([('kinds','a'), ('kinds','c')]).encode()
  req = _make_request(media_type='application/x-www-form-urlencoded', body=body)
  ep = LiteralListEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


# A union field with more than one non-primitive member is filled via a selector registered for the union.

class ShapeUnionEndpoint(Endpoint):
  max_body_bytes = 1024
  body_field = 'shape'
  class Fields:
    shape:Circle|Rect
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.shape}')


@ShapeUnionEndpoint.selector(Circle|Rect)
def _select_shape_union(static_type:TypeForm[Any], val:Any, ctx:Any) -> TypeForm[Any]:
  match val:
    case {'kind': 'circle'}: return Circle
    case {'kind': 'rect'}: return Rect
    case _: return static_type


@utest_run
def _() -> None:
  'Endpoint: a union field selects the concrete member type from the body.'
  req = _make_request(media_type='application/json', body=b'{"kind":"circle","radius":7}')
  ep = ShapeUnionEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(Circle(kind='circle', radius=7), ep.fields.shape)


# A union of primitive members passes a matching raw value through unconverted.
# Since path, query and form values are always str, `int|str` yields the str,
# and `int|float` rejects every str unless a selector chooses the member type to convert to.

class IntStrUnionEndpoint(Endpoint):
  class Fields:
    val:int|str
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.val}')


class IntFloatUnionEndpoint(Endpoint):
  class Fields:
    val:int|float
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.val}')


utest(dict(val='1'), endpoint_fields, IntStrUnionEndpoint, val='1') # The raw str matches the str member; no int conversion.
utest_exc(ResponseError, endpoint_fields, IntFloatUnionEndpoint, val='1') # A str matches no member of `int|float`.


class SelectedNumUnionEndpoint(Endpoint):
  class Fields:
    val:int|float
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.val}')


@SelectedNumUnionEndpoint.selector(int|float)
def _select_num(static_type:TypeForm[Any], val:Any, ctx:Any) -> TypeForm[Any]:
  return float if (isinstance(val, str) and '.' in val) else int


utest(dict(val=1), endpoint_fields, SelectedNumUnionEndpoint, val='1')
utest(dict(val=2.5), endpoint_fields, SelectedNumUnionEndpoint, val='2.5')


# Field types that no converter can be built for are developer errors, reported when converters are resolved.

class UnselectedShapeEndpoint(Endpoint):
  max_body_bytes = 1024
  body_field = 'shape'
  class Fields:
    shape:Circle|Rect
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.shape}')


# The Router resolves converters for every registered endpoint, so this fails at startup rather than on first request.
utest_exc(TypeError, Router, {'/shape': UnselectedShapeEndpoint})
utest_exc(TypeError, UnselectedShapeEndpoint, _make_request(), {}) # The same error if the class is used directly.


@utest_run
def _() -> None:
  'Router: constructing a router resolves the converters of every registered endpoint.'
  class RouterResolvedEndpoint(Endpoint):
    class Fields:
      n:int
    fields:Fields
    def handle_request(self, request:Request) -> Response:
      return Response(body=f'{self.fields.n}')
  utest_val(False, RouterResolvedEndpoint._converters_resolved)
  Router({'/n': RouterResolvedEndpoint})
  utest_val(True, RouterResolvedEndpoint._converters_resolved)


# Callable field types are rejected at class definition: the transtructor would pass the raw value through unconverted.

def _make_callable_field_endpoint() -> type[Endpoint]:
  class CallableFieldEndpoint(Endpoint):
    class Fields:
      fn:Callable[[int],int]
    fields:Fields
    def handle_request(self, request:Request) -> Response:
      return Response(body='')
  return CallableFieldEndpoint

utest_exc(TypeError, _make_callable_field_endpoint)


# Customization is mediated: not on Endpoint itself, and not after a class's field converters are resolved.

utest_exc(TypeError, Endpoint.prefigure, Point)
utest_exc(TypeError, Endpoint.selector, Point)


class LateCustomizationEndpoint(Endpoint):
  class Fields:
    n:int
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.n}')


@utest_run
def _() -> None:
  'Endpoint: customizing after the class has handled a request raises TypeError.'
  req = _make_request(query=dict(n='1'))
  ep = LateCustomizationEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(1, ep.fields.n)
  utest_exc(TypeError, LateCustomizationEndpoint.prefigure, Point)


# methods class var: normalizes to _methods frozenset.

class PostEndpoint(Endpoint):
  methods = 'POST'
  max_body_bytes = 1024
  class Fields:
    name:str
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=self.fields.name)


class MultiMethodEndpoint(Endpoint):
  methods = ('GET', 'POST')
  class Fields:
    tag:str|None
  fields:Fields
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.fields.tag}')


utest(frozenset({'POST'}), lambda: PostEndpoint._methods)
utest(frozenset({'GET', 'POST'}), lambda: MultiMethodEndpoint._methods)
utest(frozenset({'GET'}), lambda: IntEndpoint._methods) # Default is GET.


def _make_invalid_method_endpoint() -> type[Endpoint]:
  class ConnectEndpoint(Endpoint):
    methods = 'CONNECT'
    def handle_request(self, request:Request) -> Response:
      return Response(body='')
  return ConnectEndpoint

utest_exc(TypeError, _make_invalid_method_endpoint)


def _make_empty_methods_endpoint() -> type[Endpoint]:
  class EmptyMethodsEndpoint(Endpoint):
    methods = ()
    def handle_request(self, request:Request) -> Response:
      return Response(body='')
  return EmptyMethodsEndpoint

utest_exc(TypeError, _make_empty_methods_endpoint)


# Router raises MethodNotAllowedError when the request method is not in the endpoint's _methods.

utest_exc(MethodNotAllowedError, Router({'/' : PostEndpoint}).resolve_handler, _make_request()) # GET vs POST-only.


@utest_run
def _() -> None:
  'Router: MethodNotAllowedError includes Allow header.'
  try:
    Router({'/' : PostEndpoint}).resolve_handler(_make_request())
  except MethodNotAllowedError as exc:
    assert exc.headers is not None
    utest_val('POST', exc.headers.get('allow'))
  else:
    raise AssertionError('expected MethodNotAllowedError')


# Body size validation at construction (the content_length head check).

def _make_body_request(*, content_length:int|None, headers:dict[str,str]|None=None) -> Request:
  return Request(method='POST', scheme='http', host='localhost', port=80, path='/', query_str='id=1',
    headers=headers or {}, client_addr=('127.0.0.1', 0), content_length=content_length, conn=None)


@utest_run
def _() -> None:
  'Endpoint construction rejects a declared body larger than max_body_bytes.'
  # IntEndpoint.max_body_bytes is 1024.
  utest_exc(BodyTooLargeError, IntEndpoint, _make_body_request(content_length=2000), {})


@utest_run
def _() -> None:
  'Endpoint construction allows a declared body within max_body_bytes.'
  endpoint = IntEndpoint(_make_body_request(content_length=10), {})
  utest_val(1, endpoint.fields.id)


@utest_run
def _() -> None:
  'Endpoint construction allows a body with no declared length (content_length None, e.g. chunked); the size cap is'
  ' enforced later while reading.'
  endpoint = IntEndpoint(_make_body_request(content_length=None, headers={'transfer-encoding': 'chunked'}), {})
  utest_val(1, endpoint.fields.id)
