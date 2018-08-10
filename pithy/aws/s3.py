# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from mimetypes import guess_type as guess_mime_type
from pithy.fs import path_dir, path_join, make_dirs, file_status, walk_paths
from typing import Any, Callable, Dict, IO, Union
from io import BytesIO
import os
from gzip import compress as gz_compress, decompress as gz_expand
from bz2 import compress as bz2_compress, decompress as bz2_expand
from lzma import compress as xz_compress, decompress as xz_decompress
from boto3 import client as Client, Session # type: ignore

try: from brotli import compress as br_compress, decompress as br_expand, MODE_TEXT as br_MODE_TEXT # type: ignore
except ImportError:
  def br_compress(data:bytes): raise Exception('brotli module failed to import')
  def br_expand(data:bytes): raise Exception('brotli module failed to import')
  br_MODE_TEXT = -1


class S3MockError(Exception): pass


def put_bytes(client:Any, data:bytes, bucket:str, key:str, compress:str=None, is_utf8_hint=False) -> None:
  content_type, content_encoding = guess_mime_type(key)
  if content_type is None:
    content_type = 'application/octet-stream' # default to binary.
  if content_encoding == 'gzip':
    if data[:2] != b'\x1F\x8B':
      raise Exception(f"save_bytes: filname implies content-type 'gzip' but data does not: {key!r}")
  elif content_encoding == 'bzip2':
    if data[:3] != b'BZh':
      raise Exception(f"save_bytes: filname implies content-type 'bzip2' but data does not: {key!r}")
  elif content_encoding == 'xz':
    if data[:6] != b'\xF7zXZ\x00':
      raise Exception(f"save_bytes: filname implies content-type 'xz' but data does not: {key!r}")
  elif content_encoding == 'br':
    pass # Brotli defines no magic bytes/header.
  elif content_encoding is not None:
    raise Exception(f'unknown content-encoding: {content_encoding!r}')

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
  'bzip2': bz2_compress,
  'xz': xz_compress,
  'br': br_compress, # TODO: choose the utf8 mode when we are compressing data encoded from a string.
}



class S3Client:
  '''
  Because boto3 generates clients dynamically,
  for now we create a fake base class for mypy to refer to.
  In the future this will become a functioning, statically typed wrapper of the real S3 client.
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
        'LastModified': s.mtime,
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
