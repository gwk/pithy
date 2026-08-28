# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import io
from dataclasses import dataclass, field
from functools import cached_property
from http import HTTPStatus
from json import JSONDecodeError
from typing import Any
from urllib.parse import parse_qsl

from multipart import MultipartError, MultipartParser, parse_options_header

from ..http import http_methods
from ..json import Json, parse_json
from .errors import BadRequestError, decode_or_bad_request
from .requestconn import AddrPair, RequestConn
from .response import ResponseError


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
  except KeyError: d[k] = v # Add first value as scalar.
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
  * prevent_client_caching: whether handlers should avoid conditional or cacheable responses.
  * conn: RequestConn object for reading the request body. TODO: privatize.
  * ctx: an empty dictionary for applications to attach request state.
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
  prevent_client_caching:bool = False
  conn:RequestConn|None = None
  ctx:dict[str,Any] = field(default_factory=dict)


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
    'Parse and cache the query string into a list of (key, value) pairs.'
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


  def body_params(self, max_bytes:int, *, body_field:str='') -> dict[str,Any]:
    '''
    Parse and cache the request body based on media type and return a dict mapping parameter names to values.
    If `body_field` is non-empty, the entire parsed body is returned as a single param under that key, regardless of
    media type; for JSON this skips the requirement that the body be an object, so any JSON value (object, array, or
    scalar) becomes the single param.
    '''
    match self.media_type:
      case 'application/x-www-form-urlencoded':
        data:Any = self.parse_urlencoded(max_bytes=max_bytes)
      case 'application/json':
        data = self.parse_json(max_bytes=max_bytes)
        if not body_field and not isinstance(data, dict):
          raise BadRequestError('Expected JSON object in request body.')
      case 'multipart/form-data':
        data = self.parse_multipart(max_bytes=max_bytes)
      case _:
        raise ResponseError(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE, reason=f'Unsupported media type: {self.media_type!r}.')
    return {body_field: data} if body_field else data


  def parse_multipart(self, max_bytes:int) -> dict[str,MultipartVal|list[MultipartVal]]:
    '''Parse a multipart/form-data body. Text fields become str values; file parts become UploadedFile values.'''
    if self.media_type != 'multipart/form-data':
      raise ValueError(f'parse_multipart: expected media type multipart/form-data; received: {self.media_type!r}')
    _, options = parse_options_header(self.content_type)
    boundary = options.get('boundary', '')
    if not boundary: raise BadRequestError('parse_multipart: missing boundary parameter in Content-Type header')
    body = self.read_body(max_bytes=max_bytes)
    result:dict[str,MultipartVal|list[MultipartVal]] = {}
    # Setting spool_limit and memory_limit to the body size keeps all parts in memory without tripping either limit,
    # since part payloads are strictly smaller than the body.
    parser = MultipartParser(io.BytesIO(body), boundary=boundary, content_length=len(body), spool_limit=len(body),
      memory_limit=len(body))
    try:
      for part in parser:
        if part.name is None: raise BadRequestError('parse_multipart: part missing name parameter')
        if part.filename is None: # Text field.
          try: val = part.value
          except (UnicodeDecodeError, LookupError) as e: raise BadRequestError(f'parse_multipart: field value: {e}') from e
          _add_to_param_dict(result, part.name, val)
        elif part.filename == '': continue # File input was left empty; skip it.
        else:
          _add_to_param_dict(result, part.name, UploadedFile(
            field_name=part.name,
            filename=part.filename,
            data=part.raw,
            content_type=part.content_type,
          ))
    except MultipartError as e:
      raise BadRequestError(f'parse_multipart: {e}') from e
    return result


  def parse_urlencoded(self, max_bytes:int) -> dict[str,str|list[str]]:
    '''Parse an application/x-www-form-urlencoded body.'''
    if self.media_type != 'application/x-www-form-urlencoded':
      raise ValueError(f'parse_urlencoded: expected media type application/x-www-form-urlencoded; received: {self.media_type!r}')
    body = self.read_body(max_bytes=max_bytes)
    parsed_list = parse_qsl(decode_or_bad_request(body, desc='parse_urlencoded: body'), keep_blank_values=True)
    result:dict[str,str|list[str]] = {}
    for (k, v) in parsed_list:
      _add_to_param_dict(result, k, v)
    return result


  def parse_json(self, max_bytes:int) -> Json:
    '''Parse an application/json body.'''
    if self.media_type != 'application/json':
      raise ValueError(f'parse_json: expected media type application/json; received: {self.media_type!r}')
    body = self.read_body(max_bytes=max_bytes)
    try: return parse_json(decode_or_bad_request(body, desc='parse_json: body'))
    except JSONDecodeError as e:
      raise BadRequestError(f'Invalid JSON in request body: {e}') from e


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
