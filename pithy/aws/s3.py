# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from boto3 import client as Client, Session # type: ignore
from datetime import datetime as DateTime
from gzip import compress as gz_compress, decompress as gz_expand
from io import BytesIO
from mimetypes import guess_type as guess_mime_type
from ..fs import path_dir, path_join, make_dirs, file_status, walk_paths
from json import dumps as render_json, loads as parse_json
from typing import Any, Callable, Dict, IO, Union
import os


# Brotli compression is supported by major browsers and AWS. Pithy treats it as optional.
def br_compress(data:bytes) -> bytes: raise Exception('brotli module failed to import')
def br_expand(data:bytes) -> bytes: raise Exception('brotli module failed to import')
br_MODE_TEXT = -1
try: from brotli import compress as br_compress, decompress as br_expand, MODE_TEXT as br_MODE_TEXT # type: ignore
except ImportError: pass


class S3MockError(Exception): pass


def get_bytes(client:Any, bucket:str, key:str) -> bytes:
  r = client.get_object(Bucket=bucket, Key=key)
  body: bytes = r['Body'].read()
  encoding = r['ResponseMetadata']['HTTPHeaders'].get('content-encoding')
  if encoding == 'gzip': return gz_expand(body)
  elif encoding == 'br': return br_expand(body)
  elif encoding: raise ValueError(encoding)
  return body
  #text = GzipFile(None, 'rb', fileobj=BytesIO(compressed_body)).read().decode()
  #d:Dict[str,Any] = parse_json(text)


def get_json(client:Any, bucket:str, key:str) -> Any:
  return parse_json(get_bytes(client=client, bucket=bucket, key=key))


def put_bytes(client:Any, data:bytes, bucket:str, key:str, compress:str=None, is_utf8_hint=False) -> None:
  content_type, content_encoding = guess_mime_type(key)

  # Validate that the implied encoding appears to be the actual encoding.
  if content_type is None:
    content_type = 'application/octet-stream' # default to binary.
  if content_encoding == 'gzip':
    if data[:2] != b'\x1F\x8B':
      raise Exception(f"save_bytes: filname implies content-type 'gzip' but data does not: {key!r}")
  elif content_encoding == 'br':
    pass # Brotli defines no magic bytes/header.
  elif content_encoding is not None:
    raise Exception(f'unknown content-encoding: {content_encoding!r}')

  # Compress as requested.
  if compress is not None:
    if content_encoding is not None:
      raise Exception(f"save_bytes: key {key!r} implies content-type {content_type!r}, but `compress` is also specified: {compress!r}")
    kwargs:Dict[str,Any] = {}
    if compress == 'br' and is_utf8_hint:
      kwargs['mode'] = br_MODE_TEXT
    compress_fn = compressors[compress]
    data = compress_fn(data, **kwargs)
    content_encoding = compress

  result = client.put_object(
    Bucket=bucket,
    Key=key,
    ContentType=content_type,
    ContentEncoding=compress,
    Body=data)


compressors:Dict[str, Callable[..., Any]] = {
  'gzip' : gz_compress,
  'br': br_compress,
}


def put_json(client:Any, obj:Any, bucket:str, key:str, compress:str=None) -> None:
  data = render_json(obj).encode('utf8')
  put_bytes(client=client, data=data, bucket=bucket, key=key, compress=compress, is_utf8_hint=True)



class S3Client:
  '''
  Because boto3 generates clients dynamically,
  for now we create a fake base class for mypy to refer to.
  In the future this could become a functioning, statically typed wrapper of the real S3 client.
  '''

  def __init__(self, bucket_paths:Dict[str,str],
    aws_access_key_id:str=None,
    aws_secret_access_key:str=None,
    aws_session_token:str=None,
    config:Any=None,
    region_name:str=None,
   ) -> None:
    raise NotImplementedError

  def get_object(self, Bucket:str, Key:str) -> Dict[str,Any]:
    raise NotImplementedError

  def list_objects_v2(self, Bucket:str) -> Dict[str,Any]:
    raise NotImplementedError

  def put_object(self, Bucket:str, Key:str, ContentType:str, ContentEncoding:str, Body:bytes) -> Dict[str,Any]:
    raise NotImplementedError

  def upload_file(self, path:str, Bucket:str, Key:str) -> Dict[str,Any]:
    raise NotImplementedError



class S3MockClient(S3Client):
  '''
  A local mock of S3 that reads and writes to a provided directory for each bucket.
  '''

  def __init__(self, bucket_paths:Dict[str,str],
    aws_access_key_id:str=None,
    aws_secret_access_key:str=None,
    aws_session_token:str=None,
    config:Any=None,
    region_name:str=None,
   ) -> None:
    self._bucket_paths = bucket_paths


  def _bucket_path(self, bucket:str) -> str:
    try: return self._bucket_paths[bucket]
    except KeyError as e: raise S3MockError(f'mock bucket not found: {bucket!r}') from e


  def _open(self, bucket:str, key:str, mode:str) -> IO[Any]:
    bucket_path = self._bucket_path(bucket)
    dir = path_join(bucket_path, path_dir(key))
    make_dirs(dir)
    try: return open(path_join(bucket_path, key), mode)
    except KeyError as e: raise S3MockError(f'mock key not found: {key!r}')


  def get_object(self, Bucket:str, Key:str) -> Dict[str,Any]:
    with self._open(Bucket, Key, 'rb') as f:
      return {
        'Body': BytesIO(f.read())
      }


  def list_objects_v2(self, Bucket:str) -> Dict[str,Any]:
    path = self._bucket_path(Bucket)
    assert not path.endswith('/')
    l = len(path) + 1 # Eat the directory slash.
    contents = []
    for p in walk_paths(path):
      key = p[l:]
      s = file_status(p)
      assert s is not None
      contents.append({
        'Key': key,
        'Size': s.size,
        'LastModified': DateTime.fromtimestamp(s.mtime),
      })
    return {
      'KeyCount': len(contents),
      'Contents': contents,
    }


  def put_object(self, Bucket:str, Key:str, ContentType:str, ContentEncoding:str, Body:bytes) -> Dict[str,Any]:
    with self._open(Bucket, Key, 'wb') as f:
      f.write(Body)
    return {}


  def upload_file(self, path:str, Bucket:str, Key:str) -> Dict[str,Any]:
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
    bucket_paths:Dict[str, str] = {}
    for s in os.environ['S3_MOCK_CLIENT'].split():
      b, s, p = s.partition('=')
      if not b: raise ValueError(f'S3_MOCK_CLIENT word is not valid bucket name or `bucket=path` pair: {s!r}')
      if not s: p = b
      elif not p: raise ValueError(f'S3_MOCK_CLIENT bucket path is not valid: {s!r}')
      if b in bucket_paths: raise KeyError(f'S3_MOCK_CLIENT repeated bucket: {b!r}')
      bucket_paths[b] = p
    return S3MockClient(bucket_paths=bucket_paths, **kwargs)
  return session.client('s3', **kwargs) # type: ignore
