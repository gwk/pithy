# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import io
from dataclasses import dataclass
from functools import cached_property
from http import HTTPStatus
from typing import Iterator
from urllib.parse import parse_qs

from python_multipart import parse_form
from python_multipart.multipart import Field, File

from ..http import http_methods
from ..json import parse_json
from .errors import bad_request, decode_or_bad_request
from .response import ResponseError


type AddrPair = tuple[str,int]


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


class RequestConn:
  '''
  Abstract base class for the Request object's connection, used to read the request body.
  The actual implementation is server-specific.
  '''
  content_length:int|None # None implies chunked transfer encoding.
  transfer_encoding_compression:str|None


  def read_some(self, max_bytes:int) -> bytes:
    '''
    Read some bytes from the request body.
    `max_bytes` is the total number of bytes to be read.
    '''
    raise NotImplementedError


  def read_body(self, max_bytes:int) -> bytes:
    '''
    Read the request body.
    If the body is more than `max_bytes`, the server should close the connection and return an error response.
    '''
    raise NotImplementedError


  def read_body_to_file_path(self, max_bytes:int, file_path:str='') -> str:
    '''
    Read the request body and write it to a file at `file_path`.
    If the body is more than `max_bytes`, the server should close the connection and return an error response.
    '''
    raise NotImplementedError


  def stream_body(self, max_bytes:int, chunk_size:int=16_384) -> Iterator[bytes]:
    '''
    Stream the request body in chunks of `chunk_size` bytes.
    If the body is more than `max_bytes`, the server should close the connection and return an error response.
    '''
    raise NotImplementedError


@dataclass
class Request:
  method:str
  scheme:str
  host:str
  port:int
  path:str
  query:str
  headers:dict[str,str]
  client_addr:AddrPair  # Remote (host, port) of the connected client.
  content_length:int|None # None indicates chunked transfer encoding.
  conn:RequestConn|None = None


  def __post_init__(self) -> None:
    if self.method not in http_methods: raise bad_request('Unrecognized method.')
    if self.content_length:
      if self.content_length < 0: raise bad_request('Negative content-length.')


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


  def parse_multipart(self, max_bytes:int) -> dict[str,list[str|UploadedFile]]:
    '''Parse a multipart/form-data body. Text fields become str values; file parts become UploadedFile values.'''
    if self.media_type != 'multipart/form-data':
      raise ValueError(f'parse_multipart: expected media type multipart/form-data; received: {self.media_type!r}')
    body = self.read_body(max_bytes=max_bytes)
    result:dict[str,list[str|UploadedFile]] = {}

    def on_field(field:Field) -> None:
      if field.field_name is None: raise bad_request('parse_multipart: field part missing name parameter')
      key = decode_or_bad_request(field.field_name, desc='parse_multipart: field name')
      val = decode_or_bad_request(field.value or b'', desc='parse_multipart: field value')
      result.setdefault(key, []).append(val)

    def on_file(file:File) -> None:
      if file.field_name is None: raise bad_request('parse_multipart: file part missing name parameter')
      file.file_object.seek(0)
      key = decode_or_bad_request(file.field_name, desc='parse_multipart: file field name')
      filename = decode_or_bad_request(file.file_name or b'', desc='parse_multipart: file name')
      result.setdefault(key, []).append(UploadedFile(
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


  def parse_urlencoded(self, max_bytes:int) -> dict[str,list[str]]:
    '''Parse an application/x-www-form-urlencoded body.'''
    if self.media_type != 'application/x-www-form-urlencoded':
      raise ValueError(f'parse_urlencoded: expected media type application/x-www-form-urlencoded; received: {self.media_type!r}')
    body = self.read_body(max_bytes=max_bytes)
    return parse_qs(decode_or_bad_request(body, desc='parse_urlencoded: body'), keep_blank_values=True)


  def parse_json(self, max_bytes:int) -> object:
    '''Parse an application/json body.'''
    if self.media_type != 'application/json':
      raise ValueError(f'parse_json: expected media type application/json; received: {self.media_type!r}')
    body = self.read_body(max_bytes=max_bytes)
    return parse_json(decode_or_bad_request(body, desc='parse_json: body'))


  def allow_methods(self, *methods:str) -> None:
    '''
    If the current request method is one of the specified methods, return. Otherwise raise 405 Method Not Allowed.
    This should be called by handle_request to enforce the allowed methods.
    '''
    if self.method not in methods: raise ResponseError(status=HTTPStatus.METHOD_NOT_ALLOWED)


  def read_body(self, max_bytes:int) -> bytes:
    '''
    Read the request body.
    If the body is more than `max_bytes`, the server should close the connection and return an error response.
    '''
    if self.conn is None: raise ValueError('Request connection is not set.')
    return self.conn.read_body(max_bytes)
