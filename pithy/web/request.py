# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from http import HTTPStatus
from typing import BinaryIO

from ..http import http_methods
from ..util import lazy_property
from .errors import BadRequest
from .response import ResponseError


type AddrPair = tuple[str,int]


@dataclass
class Request:
  method:str
  scheme:str
  host:str
  port:int
  path:str
  query:str
  body_file:BinaryIO
  headers:dict[str,str]
  client_addr:AddrPair  # Remote (host, port) of the connected client.
  content_length:int = -1


  def __post_init__(self) -> None:
    if self.method not in http_methods: raise BadRequest('Unrecognized method.')
    if self.content_length < 0:
      try: self.content_length = int(self.headers.get('content-length', 0))
      except ValueError: raise BadRequest('Non-integer content-length header.')


  @lazy_property
  def path_parts(self) -> list[str]:
    assert self.path.startswith('/')
    parts = self.path.split('/')
    if not parts[-1]: del parts[-1]
    del parts[0]
    return parts


  @lazy_property
  def body_bytes(self) -> bytes:
    try: return self.body_file.read(self.content_length) if self.content_length else b''
    except Exception as exc: raise BadRequest('Failed to read request body') from exc


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
