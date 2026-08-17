# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import json as _json
from hashlib import sha1
from os import path
from tempfile import TemporaryDirectory
from typing import Any, cast, Iterator

import requests
from pithy.json import Json, JsonDict
from pithy.secrets import SecretStr
from tap_backblaze.api.client import B2Client
from tap_backblaze.api.errors import B2Error, B2IntegrityError, B2TooManyRequests
from utest import utest_exc, utest_seq, utest_val


class FakeResponse:
  'A canned HTTP response.'

  def __init__(self, status:int=200, json_body:Json=None, text:str='', headers:dict[str,str]|None=None,
   content:bytes=b'') -> None:
    self.status_code = status
    self._json = json_body
    self.headers = headers or {}
    self.content = content
    self.text = _json.dumps(json_body) if json_body is not None else text

  def json(self) -> Json:
    if self._json is None: raise ValueError('FakeResponse has no JSON body.')
    return self._json

  def iter_content(self, chunk_size:int=1) -> Iterator[bytes]:
    for i in range(0, len(self.content), chunk_size):
      yield self.content[i:i+chunk_size]


class FakeSession:
  'A session driven by a scripted queue of responses (or exceptions to raise), recording every request.'

  def __init__(self, script:list[FakeResponse|BaseException]) -> None:
    self.script = list(script)
    self.calls:list[dict[str,Any]] = []

  def request(self, method:str, url:str, *, timeout:float|None=None, headers:dict[str,str]|None=None,
   json:JsonDict|None=None, data:Any=None, auth:tuple[str,str]|None=None, stream:bool=False) -> FakeResponse:
    body = None
    if data is not None:
      chunks = []
      while chunk := data.read(1 << 12):
        chunks.append(chunk)
      body = b''.join(chunks)
    self.calls.append(dict(method=method, url=url, headers=dict(headers or {}), json=json, body=body, auth=auth))
    assert self.script, f'FakeSession script exhausted; call: {method} {url}'
    item = self.script.pop(0)
    if isinstance(item, BaseException): raise item
    return item

  def endpoints(self) -> list[str]:
    'The final URL path component of each request, for terse assertions.'
    return [call['url'].rsplit('/', 1)[-1].split('?')[0] for call in self.calls]


def auth_response(*, recommended:int=100, minimum:int=4, token:str='tok1') -> FakeResponse:
  return FakeResponse(json_body={
    'accountId': 'acct', 'authorizationToken': token,
    'apiInfo': {'storageApi': {
      'apiUrl': 'https://api001.test', 'downloadUrl': 'https://f001.test',
      'recommendedPartSize': recommended, 'absoluteMinimumPartSize': minimum,
      'allowed': {'buckets': None, 'capabilities': ['listFiles', 'readFiles', 'writeFiles'], 'namePrefix': None}}}})


def error_response(status:int, code:str, *, retry_after:str|None=None) -> FakeResponse:
  headers = {'Retry-After': retry_after} if retry_after is not None else {}
  return FakeResponse(status=status, json_body={'status': status, 'code': code, 'message': f'{code} message'},
    headers=headers)


def file_version_json(*, file_id:str='4_fid', name:str='obj.db', size:int=1, sha:str='e'*40, action:str='upload',
 file_info:JsonDict|None=None) -> JsonDict:
  return {'fileId': file_id, 'fileName': name, 'action': action, 'contentLength': size, 'contentSha1': sha,
    'fileInfo': file_info or {}, 'uploadTimestamp': 1_755_000_000_000}


def mk_client(script:list[FakeResponse|BaseException], *, max_retries:int=5) -> tuple[B2Client,FakeSession,list[float]]:
  fake = FakeSession(script)
  sleeps:list[float] = []
  client = B2Client('kid', SecretStr('ksecret'), session=cast(requests.Session, fake), sleep=sleeps.append,
    max_retries=max_retries)
  return client, fake, sleeps


# Authorize parses, caches, and uses HTTP basic auth of the credentials; a second access does not re-request.

client, fake, sleeps = mk_client([auth_response()])
auth = client.auth
utest_val('acct', auth.account_id, 'account_id')
utest_val('tok1', client.auth.auth_token.val, 'cached auth token') # Second access.
utest_val(1, len(fake.calls), 'authorize request count')
utest_val(('kid', 'ksecret'), fake.calls[0]['auth'], 'authorize basic auth')
utest_val('https://api.backblazeb2.com/b2api/v4/b2_authorize_account', fake.calls[0]['url'], 'authorize url')


# An expired auth token triggers exactly one reauthorization and the call then succeeds.

client, fake, sleeps = mk_client([
  auth_response(token='tok1'),
  error_response(401, 'expired_auth_token'),
  auth_response(token='tok2'),
  FakeResponse(json_body={'buckets': []}),
])
utest_val({'buckets': []}, client.post_json('b2_list_buckets', {'accountId': 'acct'}), 'post_json after refresh')
utest_seq(['b2_authorize_account', 'b2_list_buckets', 'b2_authorize_account', 'b2_list_buckets'], fake.endpoints)
utest_val('tok2', fake.calls[3]['headers']['Authorization'], 'refreshed token used')
utest_val([], sleeps, 'no sleeps for token refresh')


# 429 and 503 retry with the expected delays, then give up after the bound, raising the right error.

client, fake, sleeps = mk_client([
  auth_response(),
  error_response(429, 'too_many_requests', retry_after='3'),
  error_response(429, 'too_many_requests'),
  error_response(429, 'too_many_requests'),
], max_retries=2)
utest_exc(B2TooManyRequests, client.post_json, 'b2_list_buckets', {})
utest_val([3.0, 2.0], sleeps, '429 delays: Retry-After, then exponential')

client, fake, sleeps = mk_client([
  auth_response(),
  error_response(503, 'service_unavailable'),
  FakeResponse(json_body={'ok': True}),
])
utest_val({'ok': True}, client.post_json('b2_x', {}), '503 then success')
utest_val([1.0], sleeps, '503 delay')


# Small upload sends the expected headers; a failed upload fetches a fresh URL rather than reusing the old one,
# and re-sends the whole body.

with TemporaryDirectory() as tmp:
  src = path.join(tmp, 'src.bin')
  content = b'hello world+snowman \xe2\x98\x83'
  with open(src, 'wb') as f: f.write(content)
  content_sha1 = sha1(content).hexdigest()

  client, fake, sleeps = mk_client([
    auth_response(recommended=1000),
    FakeResponse(json_body={'bucketId': 'bkt', 'uploadUrl': 'https://pod1.test/u1', 'authorizationToken': 'up_tok1'}),
    error_response(503, 'service_unavailable'),
    FakeResponse(json_body={'bucketId': 'bkt', 'uploadUrl': 'https://pod2.test/u2', 'authorizationToken': 'up_tok2'}),
    FakeResponse(json_body=file_version_json(name='dir/obj name.db', size=len(content), sha=content_sha1)),
  ])
  fv = client.upload_file('bkt', src, 'dir/obj name.db')
  utest_val(content_sha1, fv.sha1, 'uploaded file version sha1')
  utest_seq(['b2_authorize_account', 'b2_get_upload_url', 'u1', 'b2_get_upload_url', 'u2'], fake.endpoints)
  first, second = fake.calls[2], fake.calls[4]
  utest_val('https://pod1.test/u1', first['url'], 'first upload url')
  utest_val('https://pod2.test/u2', second['url'], 'fresh upload url after failure')
  utest_val(content, first['body'], 'first upload body')
  utest_val(content, second['body'], 're-sent upload body')
  headers = second['headers']
  utest_val('up_tok2', headers['Authorization'], 'upload auth token')
  utest_val(str(len(content)), headers['Content-Length'], 'upload content length')
  utest_val('application/octet-stream', headers['Content-Type'], 'upload content type')
  utest_val('dir/obj%20name.db', headers['X-Bz-File-Name'], 'encoded file name header')
  utest_val(content_sha1, headers['X-Bz-Content-Sha1'], 'upload sha1 header')
  utest_val([1.0], sleeps, 'upload retry delay')


# Large upload sends the expected part count and partSha1Array, and sets large_file_sha1.

with TemporaryDirectory() as tmp:
  src = path.join(tmp, 'large.bin')
  content = b'0123456789' # part_size=4: parts of 4, 4, 2 bytes.
  with open(src, 'wb') as f: f.write(content)
  whole_sha1 = sha1(content).hexdigest()
  part_sha1s = [sha1(content[0:4]).hexdigest(), sha1(content[4:8]).hexdigest(), sha1(content[8:10]).hexdigest()]

  def part_url_response(n:int) -> FakeResponse:
    return FakeResponse(json_body={'fileId': '4_large', 'uploadUrl': f'https://pod.test/part{n}',
      'authorizationToken': f'part_tok{n}'})

  client, fake, sleeps = mk_client([
    auth_response(recommended=100, minimum=2),
    FakeResponse(json_body={'fileId': '4_large'}), # b2_start_large_file.
    part_url_response(1), FakeResponse(json_body={}),
    part_url_response(2), FakeResponse(json_body={}),
    part_url_response(3), FakeResponse(json_body={}),
    FakeResponse(json_body=file_version_json(file_id='4_large', size=len(content), sha='none',
      file_info={'large_file_sha1': whole_sha1})), # b2_finish_large_file.
  ])
  fv = client.upload_file('bkt', src, 'obj.db', part_size=4)
  utest_val(whole_sha1, fv.sha1, 'large file sha1 via file info fallback')
  utest_seq(['b2_authorize_account', 'b2_start_large_file', 'b2_get_upload_part_url', 'part1', 'b2_get_upload_part_url',
    'part2', 'b2_get_upload_part_url', 'part3', 'b2_finish_large_file'], fake.endpoints)
  start = fake.calls[1]['json']
  utest_val({'large_file_sha1': whole_sha1}, start['fileInfo'], 'start fileInfo')
  utest_val('obj.db', start['fileName'], 'start fileName is not percent-encoded')
  for i, (lo, hi) in enumerate([(0, 4), (4, 8), (8, 10)]):
    call = fake.calls[3 + 2*i]
    utest_val(content[lo:hi], call['body'], f'part {i+1} body')
    utest_val(str(i+1), call['headers']['X-Bz-Part-Number'], f'part {i+1} number')
    utest_val(part_sha1s[i], call['headers']['X-Bz-Content-Sha1'], f'part {i+1} sha1')
  utest_val({'fileId': '4_large', 'partSha1Array': part_sha1s}, fake.calls[8]['json'], 'finish partSha1Array')


# KeyboardInterrupt mid-upload cancels the large file and propagates.

with TemporaryDirectory() as tmp:
  src = path.join(tmp, 'large.bin')
  with open(src, 'wb') as f: f.write(b'0123456789')

  client, fake, sleeps = mk_client([
    auth_response(recommended=100, minimum=2),
    FakeResponse(json_body={'fileId': '4_large'}),
    FakeResponse(json_body={'fileId': '4_large', 'uploadUrl': 'https://pod.test/part1', 'authorizationToken': 'pt1'}),
    KeyboardInterrupt(),
    FakeResponse(json_body={'fileId': '4_large'}), # b2_cancel_large_file.
  ])
  utest_exc(KeyboardInterrupt, client.upload_file, 'bkt', src, 'obj.db', part_size=4)
  utest_val('b2_cancel_large_file', fake.endpoints()[-1], 'cancel after interrupt')
  utest_val({'fileId': '4_large'}, fake.calls[-1]['json'], 'cancel file id')


# list_file_versions paginates, filters on exact name and action == "upload", and stops at the first sibling name.

client, fake, sleeps = mk_client([
  auth_response(),
  FakeResponse(json_body={'files': [
      file_version_json(file_id='f1', name='obj.db'),
      file_version_json(file_id='f2', name='obj.db', action='hide'),
    ], 'nextFileName': 'obj.db', 'nextFileId': 'f3'}),
  FakeResponse(json_body={'files': [
      file_version_json(file_id='f3', name='obj.db'),
      file_version_json(file_id='f4', name='obj.db.old'), # A sibling sharing the prefix terminates iteration.
    ], 'nextFileName': 'obj.db.old', 'nextFileId': 'f5'}),
])
utest_seq(['f1', 'f3'], lambda: (fv.file_id for fv in client.list_file_versions('bkt', 'obj.db')))
utest_val({'bucketId': 'bkt', 'prefix': 'obj.db', 'startFileName': 'obj.db', 'maxFileCount': 1000},
  fake.calls[1]['json'], 'first page params')
utest_val({'bucketId': 'bkt', 'prefix': 'obj.db', 'startFileName': 'obj.db', 'startFileId': 'f3', 'maxFileCount': 1000},
  fake.calls[2]['json'], 'second page params')


# Download writes the file and verifies length and sha1; a mismatch of either is reported.

download_content = b'downloaded database bytes'
download_sha1 = sha1(download_content).hexdigest()

def download_response(*, content:bytes=download_content, sha:str=download_sha1, length:int|None=None) -> FakeResponse:
  return FakeResponse(content=content, headers={
    'Content-Length': str(length if length is not None else len(content)), 'X-Bz-Content-Sha1': sha})

with TemporaryDirectory() as tmp:
  dst = path.join(tmp, 'dst.bin')
  client, fake, sleeps = mk_client([auth_response(), download_response()])
  client.download_file_by_id('4_fid', dst)
  with open(dst, 'rb') as rf: utest_val(download_content, rf.read(), 'downloaded bytes')
  utest_val('https://f001.test/b2api/v4/b2_download_file_by_id?fileId=4_fid', fake.calls[1]['url'], 'download url')

  client, fake, sleeps = mk_client([auth_response(), download_response(sha='f'*40)])
  utest_exc(B2IntegrityError, client.download_file_by_id, '4_fid', path.join(tmp, 'bad_sha.bin'))

  client, fake, sleeps = mk_client([auth_response(), download_response(length=len(download_content) + 1)])
  utest_exc(B2IntegrityError, client.download_file_by_id, '4_fid', path.join(tmp, 'bad_len.bin'))

  # A 404 raises B2Error without writing the file.
  client, fake, sleeps = mk_client([auth_response(), error_response(404, 'not_found')])
  utest_exc(B2Error, client.download_file_by_id, 'nope', path.join(tmp, 'missing.bin'))
  utest_val(False, path.exists(path.join(tmp, 'missing.bin')), 'no file written on 404')
