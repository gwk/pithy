# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from functools import cached_property
from typing import Callable, Self

from pithy.logs import logI
from pithy.sqlite.backup import StoredVersion

from .api import B2Client, B2FileVersion, B2Unauthorized
from .creds import B2Creds
from .progress import ProgressListener


_context_keywords_ = ['b2', 'backblaze', 'backup', 'cloud storage', 'database backup', 'file versions', 'object storage',
  'restore', 'sqlite']


class B2BackupStore:
  '''
  Backblaze B2 implementation of the `pithy.sqlite.backup.BackupStore` protocol.
  Version history is provided by B2 file versioning: uploads to the same object key accumulate versions.
  '''

  def __init__(self, creds:B2Creds|Callable[[],B2Creds], bucket_name:str, *, creds_desc:str='', client:B2Client|None=None,
   quiet:bool=False) -> None:
    '''
    Construct a store without loading credentials or accessing the network.

    `creds` may be loaded credentials or a loader called on first use and cached after success.
    Pass a loader when credentials might be unavailable during local restores.
    `creds_desc` names the credential origin (e.g. a file path) for error messages.
    `client` is injectable for tests; the default constructs one lazily from `creds`.
    If `quiet` is true then user-interruption messages are suppressed.
    The bucket id is resolved from `creds.buckets` when recorded there, so a least-privilege key
    without `listBuckets` works.
    '''
    self.name = bucket_name
    self.quiet = quiet
    self._client = client
    self._creds_source = creds
    self._creds_desc = creds_desc


  @cached_property
  def client(self) -> B2Client:
    'The injected client, or a client constructed lazily from the credentials.'
    if self._client is not None: return self._client
    creds = self._creds
    return B2Client(creds.key_id, creds.key_secret)


  @cached_property
  def _creds(self) -> B2Creds:
    return self._creds_source() if callable(self._creds_source) else self._creds_source


  @cached_property
  def _authorized_client(self) -> B2Client:
    try:
      self.client.authorize()
    except B2Unauthorized:
      exit(f'Unauthorized: invalid B2 credentials{f": {self._creds_desc!r}" if self._creds_desc else ""}.')
    return self.client


  @cached_property
  def bucket_id(self) -> str:
    client = self._authorized_client
    return self._creds.buckets.get(self.name) or client.get_bucket_by_name(self.name).id


  @classmethod
  def from_creds_path(cls, creds_path:str, bucket_name:str) -> Self:
    'Construct a store that loads the credential file only when a remote operation needs it.'
    return cls(lambda: B2Creds.load(creds_path), bucket_name, creds_desc=creds_path)


  def upload(self, path:str, obj_key:str) -> bool:
    try:
      with ProgressListener('Upload progress') as progress:
        self.client.upload_file(self.bucket_id, path, obj_key, progress=progress)
      return True
    except KeyboardInterrupt:
      if not self.quiet: logI('Upload interrupted by user.')
      return False


  def list_versions(self, obj_key:str) -> list[StoredVersion]:
    return [stored_version_for_b2(fv, obj_key=obj_key) for fv in self.client.list_file_versions(self.bucket_id, obj_key)]


  def download(self, version:StoredVersion, dst_path:str) -> bool:
    try:
      with ProgressListener('Download progress') as progress:
        self._authorized_client.download_file_by_id(version.key, dst_path, progress=progress)
      return True
    except KeyboardInterrupt:
      if not self.quiet: logI('Download interrupted by user.')
      return False



def stored_version_for_b2(fv:B2FileVersion, *, obj_key:str) -> StoredVersion:
  return StoredVersion(key=fv.file_id, obj_key=obj_key, size=fv.content_length, sha1=fv.sha1, uploaded_at=fv.uploaded_at)
