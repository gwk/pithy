# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Iterator


type AddrPair = tuple[str,int]


class BodyAlreadyReadError(Exception):
  'Raised when the request body has already been read.'


class BodyTooLargeError(Exception):
  'Raised when the request body is larger than the maximum allowed size.'

  def __init__(self, *, length:int, max_bytes:int) -> None:
    super().__init__(f'{length=}; {max_bytes=}.')
    self.length = length
    self.max_bytes = max_bytes



class RequestConn:
  '''
  Abstract base class for the Request object's connection, used to read the request body.
  The actual implementation is server-specific.
  '''
  content_length:int|None # None implies chunked transfer encoding.


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



class BytesConn(RequestConn):
  '''
  A mock RequestConn that serves a fixed bytes body, for testing Endpoint field parsing from body params.
  '''

  def __init__(self, body:bytes) -> None:
    self.content_length = len(body)
    self.body = body

  def _check_size(self, max_bytes:int) -> None:
    if len(self.body) > max_bytes: raise BodyTooLargeError(length=len(self.body), max_bytes=max_bytes)

  def read_some(self, max_bytes:int) -> bytes:
    self._check_size(max_bytes)
    return self.body

  def read_body(self, max_bytes:int) -> bytes:
    self._check_size(max_bytes)
    return self.body

  def read_body_to_file_path(self, max_bytes:int, file_path:str='') -> str:
    self._check_size(max_bytes)
    return file_path

  def stream_body(self, max_bytes:int, chunk_size:int=16_384) -> Iterator[bytes]:
    del chunk_size
    self._check_size(max_bytes)
    yield self.body
