# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import io
from dataclasses import dataclass
from functools import cached_property
from http import HTTPStatus
from typing import cast
from urllib.parse import parse_qsl

from python_multipart import parse_form
from python_multipart.multipart import Field, File

from ..http import http_methods
from ..json import Json, parse_json
from ..type_utils import is_a
from .errors import BadRequestError, decode_or_bad_request
from .requestconn import AddrPair, RequestConn
from .response import ResponseError


class BodyAlreadyReadError(Exception):
  'Raised when the request body has already been read.'


class BodyTooLargeError(Exception):
  'Raised when the request body is larger than the maximum allowed size.'


@dataclass(slots=True, frozen=True)
class UploadedFile:
  field_name:str
  filename:str
  data:bytes
  content_type:str

  def __str__(self) -> str: return f'{self.filename} ({self.content_type}, {len(self.data)} bytes)'

type MultipartVal = str | UploadedFile

def _add_to_param_dict[V](d:dict[str,V|list[V]], k:str, v:V) -> None:
  try: existing = d[k]
  except KeyError: d[k] = v # Add first value as scalar
  else: # Existing value.
    if isinstance(existing, list): existing.append(v)
    else: d[k] = [existing, v]


@dataclass
class Request:
  '''
  An HTTP request.
  * method: HTTP method, e.g. 'GET', 'POST', etc.
  * scheme: URL scheme, e.g. 'http' or 'https'.
  * host: Host header value.
  * port: Port number.
  * path: URL path, e.g. '/items/42'.
  * query_str: raw URL query string, e.g. 'foo=bar&baz=qux'.
  * headers: HTTP headers.
    * Keys are normalized to lower case.
    * Values may be comma-separated combinations of multiple header values in the original header line.
  * client_addr: Remote (host, port) of the connected client.
  * content_length: Content-Length header value; None if not present or using chunked transfer encoding.
  * conn: RequestConn object for reading the request body. TODO: privatize.

  * path_parts: URL path split into parts by '/', e.g. ['items', '42'] for path '/items/42' (cached property).
  * content_type: Full Content-Type header value, including any parameters, e.g. 'application/json;charset=utf-8' (cached property).
  * media_type: The bare type/subtype portion of the Content-Type, e.g. 'application/json' (cached property).
    Note: per RFC 9110 the term "media type" includes parameters, but in this codebase `media_type` consistently refers to the
    bare type/subtype to support matching; use `content_type` when the parameters are needed.
  * query: Parsed query parameters (cached property). Raises BadRequestError if any parameter has multiple values.
  * query_multi: Parsed query parameters as dict of lists (cached property).
  * query_items: Parsed query parameters as list of (key, value) pairs (cached property).
  '''
  method:str
  scheme:str
  host:str
  port:int
  path:str
  query_str:str
  headers:dict[str,str]
  client_addr:AddrPair
  content_length:int|None
  conn:RequestConn|None = None


  def __post_init__(self) -> None:
    if self.method not in http_methods: raise BadRequestError('Unrecognized method.')
    if self.content_length:
      if self.content_length < 0: raise BadRequestError('Negative content-length.')


  @cached_property
  def path_parts(self) -> list[str]:
    assert self.path.startswith('/')
    parts = self.path.split('/')
    if not parts[-1]: del parts[-1]
    del parts[0]
    return parts


  @cached_property
  def content_type(self) -> str:
    return self.headers.get('content-type', '')


  @cached_property
  def media_type(self) -> str:
    _media_type, _, _ = self.content_type.partition(';')
    return _media_type.strip().lower()


  @cached_property
  def query_items(self) -> list[tuple[str,str]]:
    'Parse and cache the query string into a list of (key, value) pairs, taking the first value for each key.'
    if not self.query_str: return []
    return parse_qsl(self.query_str, keep_blank_values=True)


  @cached_property
  def query_multi(self) -> dict[str,list[str]]:
    'Parse and cache the query string into a dict of lists, preserving all values for each key.'
    qm:dict[str,list[str]] = {}
    for k, v in self.query_items:
      try: qm[k].append(v)
      except KeyError: qm[k] = [v]
    return qm


  @cached_property
  def query(self) -> dict[str,str]:
    '''
    Parse and cache the query string into a dict, enforcing that each key has only one value.
    If a key has multiple values, BadRequestError is raised.
    '''
    q = {}
    for k, v in self.query_items:
      if k in q: raise BadRequestError(f'Multiple values for query parameter {k!r}.')
      q[k] = v
    return q


  def body_params(self, max_bytes:int) -> dict[str,MultipartVal|list[MultipartVal]]:
    'Parse and cache the request body based on media type and return a dict mapping parameter names to values.'
    match self.media_type:
      case 'application/x-www-form-urlencoded':
        return cast(dict[str,MultipartVal|list[MultipartVal]], self.parse_urlencoded(max_bytes=max_bytes))
      case 'application/json':
        data = self.parse_json(max_bytes=max_bytes)
        # TODO: currently only string values are supported in JSON bodies; revisit if we want to support int/bool/nested types.
        if not is_a(data, dict[str,str]): raise BadRequestError('Expected JSON object with string values in request body.')
        return cast(dict[str,MultipartVal|list[MultipartVal]], data)
      case 'multipart/form-data':
        return self.parse_multipart(max_bytes=max_bytes)
      case _:
        raise ResponseError(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE, reason=f'Unsupported media type: {self.media_type!r}.')


  def parse_multipart(self, max_bytes:int) -> dict[str,MultipartVal|list[MultipartVal]]:
    '''Parse a multipart/form-data body. Text fields become str values; file parts become UploadedFile values.'''
    if self.media_type != 'multipart/form-data':
      raise ValueError(f'parse_multipart: expected media type multipart/form-data; received: {self.media_type!r}')
    body = self.read_body(max_bytes=max_bytes)
    result:dict[str,MultipartVal|list[MultipartVal]] = {}


    def on_field(field:Field) -> None:
      if field.field_name is None: raise BadRequestError('parse_multipart: field part missing name parameter')
      key = decode_or_bad_request(field.field_name, desc='parse_multipart: field name')
      val = decode_or_bad_request(field.value or b'', desc='parse_multipart: field value')
      _add_to_param_dict(result, key, val)

    def on_file(file:File) -> None:
      if file.field_name is None: raise BadRequestError('parse_multipart: file part missing name parameter')
      file.file_object.seek(0)
      key = decode_or_bad_request(file.field_name, desc='parse_multipart: file field name')
      filename = decode_or_bad_request(file.file_name or b'', desc='parse_multipart: file name')
      if filename == '': return
      _add_to_param_dict(result, key, UploadedFile(
        field_name=key,
        filename=filename,
        data=file.file_object.read(),
        content_type=file.content_type or 'application/octet-stream',
      ))

    headers:dict[str,bytes] = {
      'Content-Type': self.headers.get('content-type', '').encode(),
      'Content-Length': str(len(body)).encode(),
    }
    parse_form(headers, io.BytesIO(body), on_field, on_file)
    return result


  def parse_urlencoded(self, max_bytes:int) -> dict[str, str|list[str]]:
    '''Parse an application/x-www-form-urlencoded body.'''
    if self.media_type != 'application/x-www-form-urlencoded':
      raise ValueError(f'parse_urlencoded: expected media type application/x-www-form-urlencoded; received: {self.media_type!r}')
    body = self.read_body(max_bytes=max_bytes)
    parsed_list = parse_qsl(decode_or_bad_request(body, desc='parse_urlencoded: body'), keep_blank_values=True)
    result:dict[str, str|list[str]] = {}
    for (k, v) in parsed_list:
      _add_to_param_dict(result, k, v)
    return result


  def parse_json(self, max_bytes:int) -> Json:
    '''Parse an application/json body.'''
    if self.media_type != 'application/json':
      raise ValueError(f'parse_json: expected media type application/json; received: {self.media_type!r}')
    body = self.read_body(max_bytes=max_bytes)
    return parse_json(decode_or_bad_request(body, desc='parse_json: body'))


  def allow_methods(self, *methods:str) -> None:
    '''
    If the current request method is one of the specified methods, return. Otherwise raise 405 Method Not Allowed.
    This should be called by handle_request() to enforce the allowed methods.
    '''
    if self.method not in methods: raise ResponseError(status=HTTPStatus.METHOD_NOT_ALLOWED)


  def read_body(self, max_bytes:int) -> bytes:
    '''
    Read the request body.
    If the body is more than `max_bytes`, the server should close the connection and return an error response.
    '''
    if self.conn is None: raise ValueError('Request connection is not set.')
    return self.conn.read_body(max_bytes)
