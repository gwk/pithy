# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os
from datetime import datetime as DateTime, timezone as TimeZone
from gzip import compress as gz_compress, decompress as gz_expand
from io import BytesIO
from mimetypes import guess_type as guess_mime_type
from typing import Any, Callable, IO

from boto3 import Session # type: ignore[import]
from botocore.exceptions import ClientError # type: ignore[import]

from ..fs import file_status, make_dirs, path_dir, path_ext, path_join, walk_files
from ..json import parse_json, render_json


br_MODE_TEXT = -1
try:
  from brotli import compress as br_compress, decompress as br_expand, MODE_TEXT as br_MODE_TEXT # type: ignore[import, no-redef]
except ImportError:
  # Brotli compression is supported by major browsers and AWS. Pithy treats it as optional.
  def br_compress(data:bytes, mode:int=0) -> bytes: raise Exception('brotli module failed to import')
  def br_expand(data:bytes) -> bytes: raise Exception('brotli module failed to import')



class S3MockError(Exception): pass


def get_bytes(client:Any, bucket:str, key:str) -> bytes:
  r = client.get_object(Bucket=bucket, Key=key)
  body: bytes = r['Body'].read()
  encoding = r['ResponseMetadata']['HTTPHeaders'].get('content-encoding')
  if encoding is None:
    ext = path_ext(key)
    if ext == '.br': encoding = 'br'
    elif ext == '.gz': encoding = 'gzip'
    else: encoding = 'identity'
  if encoding == 'identity': return body
  elif encoding == 'br': return br_expand(body) # type: ignore[no-any-return]
  elif encoding == 'gzip': return gz_expand(body)
  raise ValueError(encoding)


def get_json(client:Any, bucket:str, key:str) -> Any:
  return parse_json(get_bytes(client=client, bucket=bucket, key=key))


def get_text(client:Any, bucket:str, key:str) -> Any:
  return get_bytes(client=client, bucket=bucket, key=key).decode()


def put_bytes(client:Any, data:bytes, bucket:str, key:str, content_encode:str='', is_utf8_hint=False) -> None:
  '''
  `content_encode` specifies an optional compression encoding, either `gzip` or `br`.
  '''
  content_type, content_encoding = guess_mime_type(key)

  # Validate that the implied encoding appears to be the actual encoding.
  if content_type is None:
    content_type = 'application/octet-stream' # default to binary.
  if content_encoding == 'gzip':
    if data[:2] != b'\x1F\x8B':
      raise Exception(f"save_bytes: filename implies content-type 'gzip' but data does not: {key!r}")
  elif content_encoding == 'br':
    pass # Brotli defines no magic bytes/header.
  elif content_encoding is not None:
    raise Exception(f'unknown content-encoding: {content_encoding!r}')

  # Compress as requested.
  if content_encode:
    if content_encoding is not None:
      raise Exception(f'save_bytes: key {key!r} implies content-type {content_type!r}, but `content_encode` is also specified: {content_encode!r}')
    kwargs:dict[str,Any] = {}
    if content_encode == 'br' and is_utf8_hint:
      kwargs['mode'] = br_MODE_TEXT
    compress_fn = compressors[content_encode]
    data = compress_fn(data, **kwargs)
    content_encoding = content_encode

  _ = client.put_object(
    Bucket=bucket,
    Key=key,
    ContentType=content_type,
    ContentEncoding=content_encoding or 'identity',
    Body=data)


compressors:dict[str, Callable[..., Any]] = {
  'br': br_compress,
  'gzip' : gz_compress,
}


def put_json(client:Any, obj:Any, bucket:str, key:str, content_encode:str='', **kwargs:Any) -> None:
  data = render_json(obj, **kwargs).encode()
  if key.endswith('.br'):
    if content_encode not in ('', 'br'):
      raise Exception(f'put_json: key {key!r} implies `br` compression but content_encode is also specified: {content_encode!r}')
    data = br_compress(data, mode=br_MODE_TEXT)
  elif key.endswith('.gz'):
    data = gz_compress(data)
    if content_encode not in ('', 'gzip'):
      raise Exception(f'put_json: key {key!r} implies `gzip` compression but content_encode is also specified: {content_encode!r}')
  put_bytes(client=client, data=data, bucket=bucket, key=key, content_encode=content_encode)


def put_text(client:Any, text:str, bucket:str, key:str, content_encode:str='') -> None:
  data = text.encode()
  if key.endswith('.br'):
    if content_encode not in ('', 'br'):
      raise Exception(f'put_text: key {key!r} implies `br` compression but content_encode is also specified: {content_encode!r}')
    data = br_compress(data, mode=br_MODE_TEXT)
  elif key.endswith('.gz'):
    data = gz_compress(data)
    if content_encode not in ('', 'gzip'):
      raise Exception(f'put_text: key {key!r} implies `gzip` compression but content_encode is also specified: {content_encode!r}')
  put_bytes(client=client, data=data, bucket=bucket, key=key, content_encode=content_encode)


class S3Client:
  '''
  Because boto3 generates clients dynamically,
  for now we create a fake base class for mypy to refer to.
  In the future this could become a functioning, statically typed wrapper of the real S3 client.
  '''

  def __init__(self, bucket_paths:dict[str,str],
    aws_access_key_id:str|None=None,
    aws_secret_access_key:str|None=None,
    aws_session_token:str|None=None,
    config: Any|None=None,
    region_name:str|None=None,
   ) -> None:
    raise NotImplementedError

  def get_object(self, Bucket:str, Key:str) -> dict[str,Any]:
    raise NotImplementedError

  def list_objects_v2(self, Bucket:str) -> dict[str,Any]:
    raise NotImplementedError

  def put_object(self, Bucket:str, Key:str, ContentType:str, ContentEncoding:str, Body:bytes) -> dict[str,Any]:
    raise NotImplementedError

  def upload_file(self, path:str, Bucket:str, Key:str) -> dict[str,Any]:
    raise NotImplementedError



class S3MockClient(S3Client):
  '''
  A local mock of S3 that reads and writes to a provided directory for each bucket.
  '''

  def __init__(self, bucket_paths:dict[str,str],
    aws_access_key_id:str|None=None,
    aws_secret_access_key:str|None=None,
    aws_session_token:str|None=None,
    config:Any|None=None,
    region_name:str|None=None,
   ) -> None:
    self._bucket_paths = bucket_paths


  def _bucket_path(self, bucket:str) -> str:
    try: return self._bucket_paths[bucket]
    except KeyError as e: raise S3MockError(f'mock bucket not found: {bucket!r}') from e


  def _open(self, bucket:str, key:str, mode:str) -> IO[Any]:
    bucket_path = self._bucket_path(bucket)
    key_dir = path_dir(key)
    assert not key_dir.startswith('/'), key_dir
    dir = path_join(bucket_path, key_dir)
    make_dirs(dir)
    path = path_join(bucket_path, key)
    try: return open(path, mode)
    except KeyError: raise S3MockError(f'mock key not found: {key!r}')


  def get_object(self, Bucket:str, Key:str) -> dict[str,Any]:
    try: f =  self._open(Bucket, Key, 'rb')
    except FileNotFoundError: pass
    else:
      encoding:str|None = None
      # TODO: metadata should be saved to disk and read, not inferred.
      # Guessing like this is not sufficiently generalized.
      if Key.endswith('.br'): encoding = 'br'
      elif Key.endswith('.gz'): encoding = 'gzip'
      with f:
        return {
          'Body': BytesIO(f.read()),
          'ResponseMetadata': {
            'HTTPHeaders': {
              'content-encoding': encoding
            }
          }
        }
    # Not found.
    error_response = {
      'Error': {
        'Code': 'NoSuchKey',
        'Key': Key,
        'Message': 'The specified key does not exist.'},
        'ResponseMetadata': {
          'HTTPHeaders': {},
          'HTTPStatusCode': 404,
        }
    }
    raise ClientError(error_response=error_response, operation_name='GetObject')


  def list_objects_v2(self, Bucket:str) -> dict[str,Any]:
    path = self._bucket_path(Bucket)
    assert not path.endswith('/')
    l = len(path) + 1 # Eat the directory slash.
    contents = []
    for p in walk_files(path):
      key = p[l:]
      s = file_status(p, follow=True)
      assert s is not None
      contents.append({
        'Key': key,
        'Size': s.size,
        'LastModified': DateTime.fromtimestamp(s.mtime, tz=TimeZone.utc),
      })
    return {
      'KeyCount': len(contents),
      'Contents': contents,
    }


  def put_object(self, Bucket:str, Key:str, ContentType:str, ContentEncoding:str, Body:bytes) -> dict[str,Any]:
    with self._open(Bucket, Key, 'wb') as f:
      f.write(Body)
    return {}


  def upload_file(self, path:str, Bucket:str, Key:str) -> dict[str,Any]:
    with open(path, 'rb') as local_f:
      data = local_f.read()
    with self._open(Bucket, Key, 'wb') as f:
      f.write(data)
    return {}



def s3_client(session:Session, **kwargs:Any) -> S3Client:
  '''
  Create an S3MockClient if the `S3_MOCK_CLIENT` environment variable is set;
  otherwise return a normal s3 client.
  '''
  if 'S3_MOCK_CLIENT' in os.environ:
    bucket_paths:dict[str, str] = {}
    for s in os.environ['S3_MOCK_CLIENT'].split():
      b, s, p = s.partition('=')
      if not b: raise ValueError(f'S3_MOCK_CLIENT word is not valid bucket name or `bucket=path` pair: {s!r}')
      if not s: p = b
      elif not p: raise ValueError(f'S3_MOCK_CLIENT bucket path is not valid: {s!r}')
      if b in bucket_paths: raise KeyError(f'S3_MOCK_CLIENT repeated bucket: {b!r}')
      bucket_paths[b] = p
    return S3MockClient(bucket_paths=bucket_paths, **kwargs)
  return session.client('s3', **kwargs) # type: ignore[no-any-return]
