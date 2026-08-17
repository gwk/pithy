# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Frozen dataclasses for B2 API responses, and the JSON parsing for each.

The B2 wire format is camelCase; these types are snake_case, so each has an explicit `from_json` classmethod.
Parsing is strict about required keys and value types, and tolerant of unknown keys for forward compatibility.
'''

from dataclasses import dataclass, field
from typing import Self

from pithy.date import DateTime
from pithy.frozendicts import frozendict
from pithy.json import Json, JsonDict
from pithy.secrets import SecretStr
from pithy.tz import tz_utc


class B2ParseError(ValueError):
  'A B2 API response payload did not match the expected shape.'


@dataclass(frozen=True)
class B2Auth:
  'The result of `b2_authorize_account`; carries the auth token and per-account URLs for all subsequent calls.'

  account_id: str
  auth_token: SecretStr
  api_url: str
  download_url: str
  recommended_part_size: int
  absolute_minimum_part_size: int
  capabilities: tuple[str,...]
  allowed_buckets: tuple['B2AllowedBucket',...] # Bucket restrictions of the key; empty means unrestricted.
  allowed_name_prefix: str|None

  @classmethod
  def from_json(cls, d:JsonDict) -> Self:
    storage = req_dict(req_dict(d, 'apiInfo'), 'storageApi')
    allowed = req_dict(storage, 'allowed')
    buckets:list[B2AllowedBucket] = []
    for b in opt_dicts(allowed, 'buckets'):
      buckets.append(B2AllowedBucket(id=req_str(b, 'id'), name=opt_str(b, 'name')))
    return cls(
      account_id=req_str(d, 'accountId'),
      auth_token=SecretStr(req_str(d, 'authorizationToken')),
      api_url=req_str(storage, 'apiUrl'),
      download_url=req_str(storage, 'downloadUrl'),
      recommended_part_size=req_int(storage, 'recommendedPartSize'),
      absolute_minimum_part_size=req_int(storage, 'absoluteMinimumPartSize'),
      capabilities=req_strs(allowed, 'capabilities'),
      allowed_buckets=tuple(buckets),
      allowed_name_prefix=opt_str(allowed, 'namePrefix'))


@dataclass(frozen=True)
class B2AllowedBucket:
  'A bucket restriction of an authorized key. `name` is None if the bucket was deleted or cannot be listed.'
  id: str
  name: str|None


@dataclass(frozen=True)
class B2Bucket:
  'A bucket, as returned by `b2_list_buckets`.'

  id: str
  name: str
  type: str
  account_id: str

  @classmethod
  def from_json(cls, d:JsonDict) -> Self:
    return cls(
      id=req_str(d, 'bucketId'),
      name=req_str(d, 'bucketName'),
      type=req_str(d, 'bucketType'),
      account_id=req_str(d, 'accountId'))


@dataclass(frozen=True)
class B2FileVersion:
  '''
  One version of a file, as returned by `b2_list_file_versions`, `b2_upload_file` and `b2_finish_large_file`.
  `content_sha1` is the raw wire value: a large file's is the literal string "none",
  and its true digest is recorded in the `large_file_sha1` file info key; the `sha1` property implements the fallback.
  '''

  file_id: str
  file_name: str
  action: str
  content_length: int
  content_sha1: str|None
  file_info: frozendict[str,str] = field(default_factory=frozendict)
  upload_timestamp: int = 0 # Milliseconds since the epoch, as reported by B2.

  @classmethod
  def from_json(cls, d:JsonDict) -> Self:
    fi_raw = d.get('fileInfo')
    file_info:dict[str,str] = {}
    if fi_raw is not None:
      if not isinstance(fi_raw, dict): raise B2ParseError(f'B2 response key "fileInfo" is not an object: {fi_raw!r}.')
      for key, val in fi_raw.items():
        if not isinstance(val, str): raise B2ParseError(f'B2 fileInfo value for {key!r} is not a string: {val!r}.')
        file_info[key] = val
    return cls(
      file_id=req_str(d, 'fileId'),
      file_name=req_str(d, 'fileName'),
      action=opt_str(d, 'action') or 'upload', # Upload responses omit the action.
      content_length=req_int(d, 'contentLength'),
      content_sha1=opt_str(d, 'contentSha1'),
      file_info=frozendict(file_info),
      upload_timestamp=req_int(d, 'uploadTimestamp'))

  @property
  def sha1(self) -> str|None:
    'The whole-file SHA1 hex digest: the content SHA1, or for large files the `large_file_sha1` file info fallback.'
    s = self.content_sha1
    if s and s != 'none': return s.removeprefix('unverified:')
    return self.file_info.get('large_file_sha1')

  @property
  def uploaded_at(self) -> DateTime:
    'The upload timestamp as a UTC datetime.'
    return DateTime.fromtimestamp(self.upload_timestamp/1000, tz=tz_utc)


@dataclass(frozen=True)
class B2UploadUrl:
  'An upload destination from `b2_get_upload_url` or `b2_get_upload_part_url`, with its own auth token.'

  url: str
  auth_token: SecretStr

  @classmethod
  def from_json(cls, d:JsonDict) -> Self:
    return cls(url=req_str(d, 'uploadUrl'), auth_token=SecretStr(req_str(d, 'authorizationToken')))


@dataclass(frozen=True)
class B2ApplicationKey:
  'An application key, as returned by `b2_list_keys`. The secret is never included.'

  key_id: str
  key_name: str
  account_id: str
  capabilities: tuple[str,...]
  bucket_ids: tuple[str,...] # Empty means unrestricted.
  name_prefix: str|None
  expiration_timestamp: int|None # Milliseconds since the epoch, or None.

  @classmethod
  def from_json(cls, d:JsonDict) -> Self:
    return cls(**cls._kwargs_from_json(d))

  @classmethod
  def _kwargs_from_json(cls, d:JsonDict) -> dict:
    return dict(
      key_id=req_str(d, 'applicationKeyId'),
      key_name=req_str(d, 'keyName'),
      account_id=req_str(d, 'accountId'),
      capabilities=req_strs(d, 'capabilities'),
      bucket_ids=opt_strs(d, 'bucketIds'),
      name_prefix=opt_str(d, 'namePrefix'),
      expiration_timestamp=opt_int(d, 'expirationTimestamp'))

  def as_json(self) -> JsonDict:
    return dict(key_id=self.key_id, key_name=self.key_name, account_id=self.account_id,
      capabilities=list(self.capabilities), bucket_ids=list(self.bucket_ids), name_prefix=self.name_prefix,
      expiration_timestamp=self.expiration_timestamp)


@dataclass(frozen=True)
class B2CreatedApplicationKey(B2ApplicationKey):
  'The result of `b2_create_key`; the secret `application_key` is only returned at creation.'

  application_key: SecretStr = SecretStr()

  @classmethod
  def from_json(cls, d:JsonDict) -> Self:
    return cls(application_key=SecretStr(req_str(d, 'applicationKey')), **cls._kwargs_from_json(d))


# Parsing helpers. These raise B2ParseError with the offending key for precise errors on unexpected payloads.


def req_val(d:JsonDict, key:str) -> Json:
  try: return d[key]
  except KeyError: raise B2ParseError(f'B2 response is missing key {key!r}; has keys: {sorted(d)}.') from None


def req_str(d:JsonDict, key:str) -> str:
  v = req_val(d, key)
  if not isinstance(v, str): raise B2ParseError(f'B2 response key {key!r} is not a string: {v!r}.')
  return v


def opt_str(d:JsonDict, key:str) -> str|None:
  v = d.get(key)
  if v is None: return None
  if not isinstance(v, str): raise B2ParseError(f'B2 response key {key!r} is not a string: {v!r}.')
  return v


def req_int(d:JsonDict, key:str) -> int:
  v = req_val(d, key)
  if not isinstance(v, int) or isinstance(v, bool): raise B2ParseError(f'B2 response key {key!r} is not an integer: {v!r}.')
  return v


def opt_int(d:JsonDict, key:str) -> int|None:
  v = d.get(key)
  if v is None: return None
  if not isinstance(v, int) or isinstance(v, bool): raise B2ParseError(f'B2 response key {key!r} is not an integer: {v!r}.')
  return v


def req_dict(d:JsonDict, key:str) -> JsonDict:
  v = req_val(d, key)
  if not isinstance(v, dict): raise B2ParseError(f'B2 response key {key!r} is not an object: {v!r}.')
  return v


def req_strs(d:JsonDict, key:str) -> tuple[str,...]:
  v = req_val(d, key)
  if not isinstance(v, list): raise B2ParseError(f'B2 response key {key!r} is not a list of strings: {v!r}.')
  strs:list[str] = []
  for el in v:
    if not isinstance(el, str): raise B2ParseError(f'B2 response key {key!r} is not a list of strings: {v!r}.')
    strs.append(el)
  return tuple(strs)


def opt_strs(d:JsonDict, key:str) -> tuple[str,...]:
  if d.get(key) is None: return ()
  return req_strs(d, key)


def req_dicts(d:JsonDict, key:str) -> list[JsonDict]:
  v = req_val(d, key)
  if not isinstance(v, list): raise B2ParseError(f'B2 response key {key!r} is not a list of objects: {v!r}.')
  dicts:list[JsonDict] = []
  for el in v:
    if not isinstance(el, dict): raise B2ParseError(f'B2 response key {key!r} is not a list of objects: {v!r}.')
    dicts.append(el)
  return dicts


def opt_dicts(d:JsonDict, key:str) -> list[JsonDict]:
  if d.get(key) is None: return []
  return req_dicts(d, key)
