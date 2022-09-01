# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from http import HTTPStatus
from io import BufferedReader
from typing import ByteString, Optional, Union

from pithy.markup import Mu


default_error_html_format = '''\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Error: {code}</title>
</head>
<body>
  <h1>Error: {code} - {reason}</h1>
</body>
</html>
'''

default_error_content_type = html_content_type = 'text/html;charset=utf-8'

http_status_response_strings = { s : f'{s.value} {s.phrase}'  for s in HTTPStatus }


class HttpContentError(Exception):
  '''
  An error that causes the current request handler to return the specified HTTP status code.
  Implementations of get_content can raise this as an alternative to returning a Content object.
  '''

  def __init__(self, status:HTTPStatus, reason:str='', headers:Optional[dict[str,str]]=None) -> None:
    self.status = status
    self.reason = reason
    self.headers = headers
    desc = http_status_response_strings[status]
    if reason: desc = f'{desc}: {reason}'
    super().__init__(desc)


HttpContentNotFound = HttpContentError(HTTPStatus.NOT_FOUND)
HttpContentNotImplemented = HttpContentError(HTTPStatus.NOT_IMPLEMENTED)


ContentBody = Union[None,str,bytes,bytearray,BufferedReader,Mu]

BinaryContentBody = Union[None,bytes,bytearray,BufferedReader]
#^ Note: normally we would use the abstract BinaryIO type
#  but mypy does not understand the difference between the unions when testing the runtime file type.
# TODO: support iterable[bytes]?


class HttpContent:
  '''
  Implementations of get_content return instances of this type for each request.
  '''
  def __init__(self, body:ContentBody, content_type:str='', last_modified:float=0.0) -> None:
    if isinstance(body, str):
      binary_body:BinaryContentBody = body.encode('utf-8', errors='replace')
    elif isinstance(body, Mu):
      binary_body = bytes(body)
    else:
      binary_body = body
    self.body = binary_body
    self.content_type = content_type
    self.last_modified = last_modified
