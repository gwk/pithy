# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from http import HTTPStatus
from typing import Iterator

from ..http import http_methods
from ..util import lazy_property
from .errors import BadRequest
from .response import ResponseError


type AddrPair = tuple[str,int]


class BodyAlreadyReadError(Exception):
  'Raised when the request body has already been read.'


class BodyTooLargeError(Exception):
  'Raised when the request body is larger than the maximum allowed size.'


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
    if self.method not in http_methods: raise BadRequest('Unrecognized method.')
    if self.content_length:
      if self.content_length < 0: raise BadRequest('Negative content-length.')


  @lazy_property
  def path_parts(self) -> list[str]:
    assert self.path.startswith('/')
    parts = self.path.split('/')
    if not parts[-1]: del parts[-1]
    del parts[0]
    return parts


  @lazy_property
  def post_params_multi(self) -> dict[str,list[str]]:
    '''
    Parse the request body as POST.
    In the case of multipart/form-data, this consumes the request input file,
    due to the stdlib implementation of parse_multipart.
    '''

    #media_type_val = self.headers.get('content-type', '')
    raise NotImplementedError('TODO: implement post_params_multi (cgi was removed in Python 3.13)')


  @lazy_property
  def post_params_single(self) -> dict[str,str]:
    params_multi = self.post_params_multi
    single = {}
    for k, vs in params_multi.items():
      if len(vs) != 1: raise BadRequest(f'POST parameter {k!r} has multiple values.')
      single[k] = vs[0]
    return single


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
