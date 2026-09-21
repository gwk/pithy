# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from os import environ
from sys import argv
from traceback import format_exception

from pithy.secrets import SecretBytes, SecretStr
from pithy.transtruct import dbg_transtruct, Transtructor
from pithy.web.endpoint import Endpoint
from pithy.web.request import Request
from pithy.web.response import Response


expected = argv[1] == '1'
assert dbg_transtruct is expected
# Changes after import must not affect either transtruct or endpoint behavior.
environ['PITHY_DBG_TRANSTRUCT'] = '0' if expected else '1'


@dataclass
class Payload:
  secret:SecretStr
  blob:SecretBytes
  count:int


secret = 'hidden-token'
blob = b'hidden-bytes'
private = 'person@example.test'
payload = dict(secret=secret, blob=blob, count=private)
ttor = Transtructor(strict=True)

for desired, val in ((Payload, payload), (Payload, [secret, blob, private]),
  (tuple[SecretStr,SecretBytes,int], [secret, blob, private]),
  (dict[str,int], {private: private}), (Payload, {private: 1})):
  try: ttor.transtruct(desired, val)
  except Exception as e:
    text = ''.join(format_exception(e))
    assert (private in text) is expected, text
    assert secret not in text and blob.decode() not in text, text
    if desired is Payload and val is payload:
      assert ('<redacted>' in text) is expected, text
      assert (e.__cause__ is not None) is expected
  else: raise AssertionError('Expected conversion failure.')


class Reject:
  def __init__(self, val:str) -> None:
    raise TypeError('constructor detail: ' + val)


try: ttor.transtruct(Reject, private)
except Exception as e:
  text = ''.join(format_exception(e))
  assert ('constructor detail: ' + private in text) is expected, text
  assert (e.__cause__ is not None) is expected
else: raise AssertionError('Expected constructor failure.')


class TestEndpoint(Endpoint):
  class Get:
    payload:Payload
  def get(self, request:Request, fields:Get) -> Response:
    return Response(body='ok')


request = Request(method='GET', scheme='http', host='localhost', port=80, path='/', query_str='',
  headers={}, client_addr=('127.0.0.1', 0), content_length=None)
try: TestEndpoint(request, path_params={'payload': payload})
except Exception as e:
  text = ''.join(format_exception(e))
  assert (private in text) is expected, text
  assert secret not in text and blob.decode() not in text, text
  assert (e.__cause__ is not None) is expected
else: raise AssertionError('Expected endpoint failure.')

print('debug: enabled' if expected else 'debug: disabled')
