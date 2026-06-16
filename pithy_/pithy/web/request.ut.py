# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus

from pithy.web.errors import BadRequestError, ResponseError
from pithy.web.request import _add_to_param_dict, Request, UploadedFile
from pithy.web.requestconn import BodyTooLargeError, BytesConn
from utest import utest_exc, utest_run, utest_val


def _make_request(media_type:str='', body:bytes=b'', query_str:str='') -> Request:
  headers:dict[str,str] = {}
  if media_type:
    headers['content-type'] = media_type
  content_length = len(body) if body else None
  conn = BytesConn(body) if body else None
  return Request(method='GET', scheme='http', host='localhost', port=80, path='/', query_str=query_str,
    headers=headers, client_addr=('127.0.0.1', 0), content_length=content_length, conn=conn)


def _make_multipart(boundary:str, *parts:bytes) -> bytes:
  b = boundary.encode()
  body = b''
  for part in parts:
    body += b'--' + b + b'\r\n' + part + b'\r\n'
  body += b'--' + b + b'--\r\n'
  return body


# _add_to_param_dict

@utest_run
def _() -> None:
  '_add_to_param_dict: first value stored as scalar.'
  d:dict = {}
  _add_to_param_dict(d, 'k', 'a')
  utest_val('a', d['k'])


@utest_run
def _() -> None:
  '_add_to_param_dict: second value with same key promotes to list.'
  d:dict = {}
  _add_to_param_dict(d, 'k', 'a')
  _add_to_param_dict(d, 'k', 'b')
  utest_val(['a', 'b'], d['k'])


@utest_run
def _() -> None:
  '_add_to_param_dict: third value appends to existing list.'
  d:dict = {}
  _add_to_param_dict(d, 'k', 'a')
  _add_to_param_dict(d, 'k', 'b')
  _add_to_param_dict(d, 'k', 'c')
  utest_val(['a', 'b', 'c'], d['k'])


@utest_run
def _() -> None:
  '_add_to_param_dict: different keys stay independent.'
  d:dict = {}
  _add_to_param_dict(d, 'x', '1')
  _add_to_param_dict(d, 'y', '2')
  _add_to_param_dict(d, 'x', '3')
  utest_val(['1', '3'], d['x'])
  utest_val('2', d['y'])


# parse_urlencoded

@utest_run
def _() -> None:
  'parse_urlencoded: simple key/value pairs parse correctly.'
  req = _make_request('application/x-www-form-urlencoded', b'name=alice&count=3')
  utest_val({'name': 'alice', 'count': '3'}, req.parse_urlencoded(max_bytes=1024))


@utest_run
def _() -> None:
  'parse_urlencoded: multi-value same key produces a list.'
  req = _make_request('application/x-www-form-urlencoded', b'tag=a&tag=b&tag=c')
  utest_val({'tag': ['a', 'b', 'c']}, req.parse_urlencoded(max_bytes=1024))


@utest_run
def _() -> None:
  'parse_urlencoded: bad encoding raises BadRequestError.'
  req = _make_request('application/x-www-form-urlencoded', b'\x80\x81')
  utest_exc(BadRequestError, req.parse_urlencoded, max_bytes=1024)


# parse_json / body_params JSON path

@utest_run
def _() -> None:
  'body_params: valid JSON object with string values parses correctly.'
  req = _make_request('application/json', b'{"name":"alice","tag":"admin"}')
  utest_val({'name': 'alice', 'tag': 'admin'}, req.body_params(max_bytes=1024))


@utest_run
def _() -> None:
  'body_params: non-object JSON raises BadRequestError.'
  req = _make_request('application/json', b'["a","b"]')
  utest_exc(BadRequestError, req.body_params, max_bytes=1024)


@utest_run
def _() -> None:
  'parse_json: malformed JSON raises BadRequestError.'
  req = _make_request('application/json', b'{not json')
  utest_exc(BadRequestError, req.parse_json, max_bytes=1024)


# query properties.

@utest_run
def _() -> None:
  'query: duplicate query keys raise BadRequestError.'
  req = _make_request(query_str='a=1&a=2')
  utest_exc(BadRequestError, lambda: req.query)


@utest_run
def _() -> None:
  'query_multi: duplicate query keys preserved as lists.'
  req = _make_request(query_str='a=1&a=2&b=3')
  utest_val({'a': ['1', '2'], 'b': ['3']}, req.query_multi)


# parse_multipart

@utest_run
def _() -> None:
  'parse_multipart: text field parses correctly.'
  boundary = 'boundary123'
  part = b'Content-Disposition: form-data; name="name"\r\n\r\nalice'
  body = _make_multipart(boundary, part)
  req = _make_request(f'multipart/form-data; boundary={boundary}', body)
  utest_val({'name': 'alice'}, req.parse_multipart(max_bytes=4096))


@utest_run
def _() -> None:
  'parse_multipart: file upload produces UploadedFile with correct fields.'
  boundary = 'boundary123'
  part = b'Content-Disposition: form-data; name="upload"; filename="test.txt"\r\nContent-Type: application/octet-stream\r\n\r\nhello'
  body = _make_multipart(boundary, part)
  req = _make_request(f'multipart/form-data; boundary={boundary}', body)
  result = req.parse_multipart(max_bytes=4096)
  f = result['upload']
  assert isinstance(f, UploadedFile)
  utest_val('upload', f.field_name)
  utest_val('test.txt', f.filename)
  utest_val(b'hello', f.data)


@utest_run
def _() -> None:
  'parse_multipart: file part with empty filename is skipped.'
  boundary = 'boundary123'
  part = b'Content-Disposition: form-data; name="upload"; filename=""\r\nContent-Type: application/octet-stream\r\n\r\nhello'
  body = _make_multipart(boundary, part)
  req = _make_request(f'multipart/form-data; boundary={boundary}', body)
  utest_val({}, req.parse_multipart(max_bytes=4096))


@utest_run
def _() -> None:
  'parse_multipart: multi-value text field produces a list.'
  boundary = 'boundary123'
  part_a = b'Content-Disposition: form-data; name="tag"\r\n\r\nalpha'
  part_b = b'Content-Disposition: form-data; name="tag"\r\n\r\nbeta'
  body = _make_multipart(boundary, part_a, part_b)
  req = _make_request(f'multipart/form-data; boundary={boundary}', body)
  utest_val({'tag': ['alpha', 'beta']}, req.parse_multipart(max_bytes=4096))


# body_params dispatch

@utest_run
def _() -> None:
  'body_params: unsupported media type raises ResponseError 415.'
  req = _make_request('text/plain', b'hello')
  try: req.body_params(max_bytes=1024)
  except ResponseError as e: utest_val(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, e.status)
  else: assert False, 'expected ResponseError'


# read_body

@utest_run
def _() -> None:
  'read_body: body exceeding max_bytes raises BodyTooLargeError.'
  req = _make_request('text/plain', b'0123456789')
  utest_exc(BodyTooLargeError, req.read_body, max_bytes=5)


@utest_run
def _() -> None:
  'read_body: body equal to max_bytes is allowed.'
  req = _make_request('text/plain', b'01234')
  utest_val(b'01234', req.read_body(max_bytes=5))


# ctx

@utest_run
def _() -> None:
  'Request.ctx defaults to an empty dict.'
  req = _make_request()
  utest_val({}, req.ctx)


@utest_run
def _() -> None:
  'Request.ctx is per-instance, not a shared mutable default.'
  a = _make_request()
  b = _make_request()
  a.ctx['user'] = 'alice'
  utest_val({}, b.ctx)
