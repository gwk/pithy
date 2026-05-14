# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from datetime import date, datetime, time
from enum import Enum
from http import HTTPStatus
from typing import Any
from urllib.parse import urlencode

from pithy.web.endpoint import Endpoint
from pithy.web.errors import ResponseError
from pithy.web.request import Request, UploadedFile
from pithy.web.requestconn import BytesConn
from pithy.web.response import Response
from utest import utest, utest_exc, utest_run, utest_val


def _make_request(query:dict[str,str|int]|None=None, *, media_type:str='', body:bytes=b'') -> Request:
  query_str = urlencode(query) if query else ''
  headers:dict[str,str] = {}
  if media_type:
    headers['content-type'] = media_type
  content_length = len(body) if body else None
  conn = BytesConn(body) if media_type else None
  return Request(method='GET', scheme='http', host='localhost', port=80, path='/', query_str=query_str, headers=headers,
    client_addr=('127.0.0.1', 0), content_length=content_length, conn=conn)


# Basic field types.

class IntEndpoint(Endpoint):
  id:int
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.id}')


class MultiFieldEndpoint(Endpoint):
  name:str
  count:int
  ratio:float
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.name},{self.count},{self.ratio}')


class OptionalEndpoint(Endpoint):
  name:str
  tag:str|None
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.name},{self.tag}')


class DateEndpoint(Endpoint):
  d:date
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.d}')


class DatetimeEndpoint(Endpoint):
  dt:datetime
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.dt}')


class TimeEndpoint(Endpoint):
  t:time
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.t}')


class BoolEndpoint(Endpoint):
  flag:bool
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.flag}')


def endpoint_fields(cls:type[Endpoint], **kwargs:str) -> dict[str,Any]:
  'Construct an endpoint with path params, prepare it, and return the populated field values.'
  request = _make_request()
  ep = cls(request=request, path_params=kwargs)
  ep.prepare(request)
  return {k: getattr(ep, k) for k in ep._fields}


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
    utest_val(True, ep.flag, desc=f'bool from {s!r}')
  for s in ('false', '0', 'no', ''):
    ep = BoolEndpoint(_make_request(), path_params=dict(flag=s))
    utest_val(False, ep.flag, desc=f'bool from {s!r}')


# Custom converters.

class Color(Enum):
  red = 'red'
  green = 'green'
  blue = 'blue'


class CustomConverterEndpoint(Endpoint):
  _converters = {Color: lambda s: Color(s)}
  color:Color

  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.color.value}')


utest(dict(color=Color.red), endpoint_fields, CustomConverterEndpoint, color='red')
utest_exc(ResponseError, CustomConverterEndpoint, _make_request(), dict(color='purple'))


# Custom converter inheritance.

class BaseConverterEndpoint(Endpoint):
  _converters = {Color: lambda s: Color(s)}


class InheritedConverterEndpoint(BaseConverterEndpoint):
  color:Color
  name:str
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.color.value},{self.name}')


utest(dict(color=Color.green, name='test'), endpoint_fields, InheritedConverterEndpoint, color='green', name='test')


# No-field endpoint.

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
  name:str
  tag:str|None
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.name},{self.tag}')

class ListEndpoint(Endpoint):
  max_body_bytes = 1024
  tags: list[str]
  counts: list[int]
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.tags},{self.counts}')


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
  utest_val(3, ep.id)


@utest_run
def _() -> None:
  'Endpoint: prepare fills list fields from JSON body with array values.'
  req = _make_request(media_type='application/json', body=b'{"tags":["a","b"],"counts":[1,2]}')
  ep = ListEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val(['a', 'b'], ep.tags)
  utest_val([1, 2], ep.counts)


@utest_run
def _() -> None:
  'Endpoint: prepare raises on nested dict value in JSON body.'
  req = _make_request(media_type='application/json', body=b'{"name":{"first":"alice"}}')
  ep = BodyEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)


# List fields.



class OptionalListEndpoint(Endpoint):
  max_body_bytes = 1024
  tags: list[str]|None
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.tags}')


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
  return {k: getattr(ep, k) for k in ep._fields}


@utest_run
def _() -> None:
  'Endpoint: list[str] field filled from urlencoded body with multiple values.'
  result = endpoint_body_fields(ListEndpoint, 'tags=a&tags=b&tags=c&counts=1&counts=2')
  utest_val(['a', 'b', 'c'], result['tags'])
  utest_val([1, 2], result['counts'])


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


# UploadedFile fields.

class UploadedFileEndpoint(Endpoint):
  max_body_bytes = 4096
  file:UploadedFile
  def handle_request(self, request:Request) -> Response:
    return Response(body=f'{self.file.filename}')


@utest_run
def _() -> None:
  'Endpoint: UploadedFile field filled from multipart body.'
  part = b'Content-Disposition: form-data; name="file"; filename="hello.txt"\r\nContent-Type: application/octet-stream\r\n\r\nhello'
  req = _multipart_request('boundary123', part)
  ep = UploadedFileEndpoint(req, path_params={})
  ep.prepare(req)
  utest_val('hello.txt', ep.file.filename)
  utest_val(b'hello', ep.file.data)


@utest_run
def _() -> None:
  'Endpoint: UploadedFile field raises BadRequestError when given a string value.'
  req = _urlencoded_request('file=not-a-file')
  ep = UploadedFileEndpoint(req, path_params={})
  utest_exc(ResponseError, ep.prepare, req)

