# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`B2Client`: request plumbing, auth, retry, upload and download for the B2 native API.
'''

import time
from hashlib import sha1
from typing import BinaryIO, Callable, cast, Iterator, Protocol, Sequence

import requests
from pithy.filestatus import file_size
from pithy.json import JsonDict
from pithy.secrets import SecretStr

from ..progress import ProgressReader
from .errors import (b2_error_for_response, B2Error, B2ExpiredAuthToken, B2IntegrityError, B2NotFound, B2Unauthorized,
  is_retryable, retry_delay)
from .types import (B2ApplicationKey, B2Auth, B2Bucket, B2CreatedApplicationKey, B2FileVersion, B2ParseError, B2UploadUrl,
  opt_str, req_dicts, req_str)
from .util import (api_url, api_version as default_api_version, compute_sha1s, download_by_id_url, encode_file_name,
  parse_retry_after, plan_part_size, plan_parts, realm_url, validate_file_name)


default_max_retries = 5
default_timeout = 128.0 # Timeout for requests: connection and read inactivity, not a total limit.
default_content_type = 'application/octet-stream'
download_chunk_size = 1 << 16
large_file_sha1_key = 'large_file_sha1' # File info key recording the whole-file digest of a large upload.


class Progress(Protocol):
  'Progress display protocol for uploads and downloads; see `tap_backblaze.progress.ProgressListener`.'

  def set_total_bytes(self, total_byte_count:int) -> None: ...

  def bytes_completed(self, byte_count:int) -> None: ...


class B2Client:
  '''
  A client for the B2 native API.
  Construction does no I/O; authorization happens lazily on first use.
  `session` and `sleep` are injectable so that retry and refresh logic is unit testable without network.
  '''

  def __init__(self, key_id:str, key_secret:SecretStr, *, session:requests.Session|None=None,
   api_version:str=default_api_version, sleep:Callable[[float],None]=time.sleep, max_retries:int=default_max_retries,
   timeout:float=default_timeout) -> None:
    self.key_id = key_id
    self.key_secret = key_secret
    self.api_version = api_version
    self.session = session if session is not None else requests.Session()
    self.sleep = sleep
    self.max_retries = max_retries
    self.timeout = timeout
    self._auth:B2Auth|None = None


  @property
  def auth(self) -> B2Auth:
    'The current authorization, obtained on first use.'
    if self._auth is None: return self.authorize()
    return self._auth


  def authorize(self) -> B2Auth:
    'Call `b2_authorize_account` and cache the result. Raises B2Unauthorized for bad credentials.'
    url = api_url(realm_url, 'b2_authorize_account', version=self.api_version)
    attempt = 0
    while True:
      try: resp = self._request('POST', url, auth=(self.key_id, self.key_secret.val), json={})
      except requests.RequestException:
        if attempt < self.max_retries:
          self.sleep(retry_delay(attempt))
          attempt += 1
          continue
        raise
      if resp.status_code == 200:
        self._auth = B2Auth.from_json(self._json_dict(resp))
        return self._auth
      error = self._error_for(resp)
      if is_retryable(error) and attempt < self.max_retries:
        self.sleep(retry_delay(attempt, error.retry_after))
        attempt += 1
        continue
      raise error


  def post_json(self, endpoint:str, params:JsonDict) -> JsonDict:
    '''
    POST a JSON API call to the per-account api URL with the account auth token; the single choke point
    for authenticated JSON calls. An expired auth token triggers exactly one reauthorization;
    retryable errors are retried with bounded exponential backoff honoring Retry-After.
    '''
    reauthorized = False
    attempt = 0
    while True:
      auth = self.auth
      url = api_url(auth.api_url, endpoint, version=self.api_version)
      try: resp = self._request('POST', url, headers={'Authorization': auth.auth_token.val}, json=params)
      except requests.RequestException:
        if attempt < self.max_retries:
          self.sleep(retry_delay(attempt))
          attempt += 1
          continue
        raise
      if resp.status_code == 200: return self._json_dict(resp)
      error = self._error_for(resp)
      if isinstance(error, B2ExpiredAuthToken) and not reauthorized:
        reauthorized = True
        self.authorize()
        continue
      if is_retryable(error) and attempt < self.max_retries:
        self.sleep(retry_delay(attempt, error.retry_after))
        attempt += 1
        continue
      raise error


  # Buckets.


  def list_buckets(self, *, bucket_name:str|None=None) -> list[B2Bucket]:
    'List the buckets of the account, optionally filtered to an exact name.'
    params:JsonDict = {'accountId': self.auth.account_id}
    if bucket_name is not None: params['bucketName'] = bucket_name
    d = self.post_json('b2_list_buckets', params)
    return [B2Bucket.from_json(b) for b in req_dicts(d, 'buckets')]


  def get_bucket_by_name(self, name:str) -> B2Bucket:
    'Resolve a bucket by exact name; raises B2NotFound if it does not exist or the key cannot list it.'
    buckets = self.list_buckets(bucket_name=name)
    if not buckets: raise B2NotFound(404, 'not_found', f'No bucket named {name!r}.')
    return buckets[0]


  # File versions.


  def list_file_versions(self, bucket_id:str, obj_key:str) -> Iterator[B2FileVersion]:
    '''
    Yield the upload versions of the exact object key, paginating as needed.
    Sibling keys that merely share the prefix are excluded, as are hide markers and unfinished uploads.
    '''
    start_name:str = obj_key
    start_id:str|None = None
    while True:
      params:JsonDict = {'bucketId': bucket_id, 'prefix': obj_key, 'startFileName': start_name, 'maxFileCount': 1000}
      if start_id is not None: params['startFileId'] = start_id
      d = self.post_json('b2_list_file_versions', params)
      for fd in req_dicts(d, 'files'):
        fv = B2FileVersion.from_json(fd)
        if fv.file_name != obj_key: return # Names are sorted, so everything after the exact matches is a sibling.
        if fv.action == 'upload': yield fv
      next_name = opt_str(d, 'nextFileName')
      if next_name is None: return # Fully paginated.
      if next_name != obj_key: return # The next page starts past the exact matches.
      start_name = next_name
      start_id = opt_str(d, 'nextFileId')


  def delete_file_version(self, file_id:str, file_name:str) -> None:
    'Delete a single file version.'
    self.post_json('b2_delete_file_version', {'fileId': file_id, 'fileName': file_name})


  # Upload.


  def upload_file(self, bucket_id:str, path:str, obj_key:str, *, content_type:str=default_content_type,
   progress:Progress|None=None, part_size:int|None=None) -> B2FileVersion:
    '''
    Upload the file at `path` as `obj_key`, dispatching on size to the small or large protocol.
    The whole-file SHA1 is computed in a pre-pass, so it is available up front for the small-file header
    and the large-file `large_file_sha1` file info.
    `part_size` overrides both the large-file threshold and the planned part size; it exists for tests.
    '''
    validate_file_name(obj_key)
    size = file_size(path)
    auth = self.auth
    threshold = part_size if part_size is not None else auth.recommended_part_size
    if progress is not None: progress.set_total_bytes(size)
    with open(path, 'rb') as f:
      if size > threshold:
        chosen_size = part_size if part_size is not None else plan_part_size(size,
          min_part_size=auth.absolute_minimum_part_size, recommended_part_size=auth.recommended_part_size)
        parts = plan_parts(size, chosen_size)
        return self._upload_large(bucket_id, f, size=size, obj_key=obj_key, content_type=content_type, parts=parts,
          progress=progress)
      else:
        return self._upload_small(bucket_id, f, size=size, obj_key=obj_key, content_type=content_type, progress=progress)


  def _upload_small(self, bucket_id:str, f:BinaryIO, *, size:int, obj_key:str, content_type:str, progress:Progress|None
   ) -> B2FileVersion:
    f.seek(0)
    whole_sha1, _ = compute_sha1s(f, [(0, size)])
    attempt = 0
    while True:
      upload = B2UploadUrl.from_json(self.post_json('b2_get_upload_url', {'bucketId': bucket_id}))
      headers = {
        'Authorization': upload.auth_token.val,
        'Content-Length': str(size),
        'Content-Type': content_type,
        'X-Bz-File-Name': encode_file_name(obj_key),
        'X-Bz-Content-Sha1': whole_sha1,
      }
      f.seek(0)
      reader = ProgressReader(f, limit=size, on_bytes=(progress.bytes_completed if progress is not None else None))
      resp = self._upload_request(upload.url, headers=headers, reader=reader, attempt=attempt)
      if resp is None: # Network failure; retry with a fresh URL.
        attempt += 1
        continue
      if resp.status_code == 200: return B2FileVersion.from_json(self._json_dict(resp))
      error = self._error_for(resp)
      # A failed upload URL must not be reused; loop around to fetch a fresh one.
      if self._upload_error_is_retryable(error) and attempt < self.max_retries:
        self.sleep(retry_delay(attempt, error.retry_after))
        attempt += 1
        continue
      raise error


  def _upload_large(self, bucket_id:str, f:BinaryIO, *, size:int, obj_key:str, content_type:str,
   parts:Sequence[tuple[int,int]], progress:Progress|None) -> B2FileVersion:
    f.seek(0)
    whole_sha1, part_sha1s = compute_sha1s(f, parts)
    start = self.post_json('b2_start_large_file', {'bucketId': bucket_id, 'fileName': obj_key, 'contentType': content_type,
      'fileInfo': {large_file_sha1_key: whole_sha1}})
    file_id = req_str(start, 'fileId')
    try:
      for idx, ((offset, part_len), part_sha1) in enumerate(zip(parts, part_sha1s, strict=True)):
        self._upload_part(f, file_id=file_id, part_number=idx+1, offset=offset, size=part_len, part_sha1=part_sha1,
          progress=progress)
      finish = self.post_json('b2_finish_large_file', {'fileId': file_id, 'partSha1Array': list(part_sha1s)})
      return B2FileVersion.from_json(finish)
    except BaseException:
      # Best-effort cancel, so an aborted upload (including KeyboardInterrupt) does not linger and accrue storage.
      try: self.post_json('b2_cancel_large_file', {'fileId': file_id})
      except Exception: pass
      raise


  def _upload_part(self, f:BinaryIO, *, file_id:str, part_number:int, offset:int, size:int, part_sha1:str,
   progress:Progress|None) -> None:
    attempt = 0
    while True:
      upload = B2UploadUrl.from_json(self.post_json('b2_get_upload_part_url', {'fileId': file_id}))
      headers = {
        'Authorization': upload.auth_token.val,
        'Content-Length': str(size),
        'X-Bz-Part-Number': str(part_number),
        'X-Bz-Content-Sha1': part_sha1,
      }
      f.seek(offset)
      on_bytes = (lambda count: progress.bytes_completed(offset + count)) if progress is not None else None
      reader = ProgressReader(f, limit=size, on_bytes=on_bytes)
      resp = self._upload_request(upload.url, headers=headers, reader=reader, attempt=attempt)
      if resp is None: # Network failure; retry with a fresh URL.
        attempt += 1
        continue
      if resp.status_code == 200: return
      error = self._error_for(resp)
      if self._upload_error_is_retryable(error) and attempt < self.max_retries:
        self.sleep(retry_delay(attempt, error.retry_after))
        attempt += 1
        continue
      raise error


  def _upload_request(self, url:str, *, headers:dict[str,str], reader:ProgressReader, attempt:int
   ) -> requests.Response|None:
    'POST an upload body; returns None (after backoff) for a network failure that should retry with a fresh URL.'
    try: return self._request('POST', url, headers=headers, data=reader)
    except requests.RequestException:
      if attempt < self.max_retries:
        self.sleep(retry_delay(attempt))
        return None
      raise


  def _upload_error_is_retryable(self, error:B2Error) -> bool:
    # Per the B2 documentation, a 401 during an upload means the upload URL's token expired or was rejected;
    # the remedy is a fresh upload URL, not account reauthorization.
    return is_retryable(error) or isinstance(error, (B2Unauthorized, B2ExpiredAuthToken))


  # Download.


  def download_file_by_id(self, file_id:str, dst_path:str, *, progress:Progress|None=None) -> None:
    '''
    Download a file version, streaming to `dst_path`.
    The body is verified against the Content-Length and X-Bz-Content-Sha1 response headers;
    a mismatch raises B2IntegrityError.
    '''
    resp = self._download_response(file_id)
    length_header = resp.headers.get('Content-Length')
    expected_len = int(length_header) if length_header is not None and length_header.isdigit() else None
    expected_sha1 = resp.headers.get('X-Bz-Content-Sha1')
    if progress is not None and expected_len is not None: progress.set_total_bytes(expected_len)
    hasher = sha1()
    count = 0
    with open(dst_path, 'wb') as out:
      for chunk in resp.iter_content(chunk_size=download_chunk_size):
        out.write(chunk)
        hasher.update(chunk)
        count += len(chunk)
        if progress is not None: progress.bytes_completed(count)
    if expected_len is not None and count != expected_len:
      raise B2IntegrityError(200, 'length_mismatch',
        f'Downloaded {count} bytes but the server reported Content-Length {expected_len}.')
    if expected_sha1 and expected_sha1 != 'none':
      exp = expected_sha1.removeprefix('unverified:')
      digest = hasher.hexdigest()
      if digest != exp:
        raise B2IntegrityError(200, 'sha1_mismatch', f'Downloaded SHA1 {digest} does not match the server digest {exp}.')


  def _download_response(self, file_id:str) -> requests.Response:
    reauthorized = False
    attempt = 0
    while True:
      auth = self.auth
      url = download_by_id_url(auth.download_url, file_id, version=self.api_version)
      try: resp = self._request('GET', url, headers={'Authorization': auth.auth_token.val}, stream=True)
      except requests.RequestException:
        if attempt < self.max_retries:
          self.sleep(retry_delay(attempt))
          attempt += 1
          continue
        raise
      if resp.status_code == 200: return resp
      error = self._error_for(resp)
      if isinstance(error, B2ExpiredAuthToken) and not reauthorized:
        reauthorized = True
        self.authorize()
        continue
      if is_retryable(error) and attempt < self.max_retries:
        self.sleep(retry_delay(attempt, error.retry_after))
        attempt += 1
        continue
      raise error


  # Application keys.


  def list_keys(self) -> list[B2ApplicationKey]:
    'List the application keys of the account, paginating as needed.'
    keys:list[B2ApplicationKey] = []
    start_id:str|None = None
    while True:
      params:JsonDict = {'accountId': self.auth.account_id, 'maxKeyCount': 1000}
      if start_id is not None: params['startApplicationKeyId'] = start_id
      d = self.post_json('b2_list_keys', params)
      keys.extend(B2ApplicationKey.from_json(kd) for kd in req_dicts(d, 'keys'))
      start_id = opt_str(d, 'nextApplicationKeyId')
      if start_id is None: return keys


  def create_key(self, name:str, capabilities:Sequence[str], bucket_ids:Sequence[str], *, name_prefix:str|None=None,
   valid_duration_seconds:int|None=None) -> B2CreatedApplicationKey:
    'Create an application key. The returned secret is only available at creation.'
    params:JsonDict = {'accountId': self.auth.account_id, 'capabilities': list(capabilities), 'keyName': name}
    if bucket_ids: params['bucketIds'] = list(bucket_ids)
    if name_prefix is not None: params['namePrefix'] = name_prefix
    if valid_duration_seconds is not None: params['validDurationInSeconds'] = valid_duration_seconds
    return B2CreatedApplicationKey.from_json(self.post_json('b2_create_key', params))


  def delete_key(self, application_key_id:str) -> None:
    'Delete an application key.'
    self.post_json('b2_delete_key', {'applicationKeyId': application_key_id})


  # Request plumbing.


  def _request(self, method:str, url:str, **kwargs:object) -> requests.Response:
    'The single point of HTTP contact; network failures raise requests.RequestException.'
    return self.session.request(method, url, timeout=self.timeout, **kwargs) # type: ignore[arg-type]


  def _error_for(self, resp:requests.Response) -> B2Error:
    return b2_error_for_response(resp.status_code, resp.text, retry_after=parse_retry_after(resp.headers.get('Retry-After')))


  def _json_dict(self, resp:requests.Response) -> JsonDict:
    body = resp.json()
    if not isinstance(body, dict): raise B2ParseError(f'B2 response body is not a JSON object: {body!r}.')
    return cast(JsonDict, body)
