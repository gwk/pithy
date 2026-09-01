# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.logs import logI
from pithy.sqlite.backup import StoredVersion

from .api import B2Client, B2FileVersion, B2Unauthorized
from .creds import B2Creds
from .progress import ProgressListener


class B2BackupStore:
  '''
  Backblaze B2 implementation of the `pithy.sqlite.backup.BackupStore` protocol.
  Version history is provided by B2 file versioning: uploads to the same object key accumulate versions.
  '''

  def __init__(self, creds:B2Creds, bucket_name:str, *, creds_desc:str='', client:B2Client|None=None,
   quiet:bool=False) -> None:
    '''
    `creds_desc` names the credential origin (e.g. a file path) for error messages.
    `client` is injectable for tests; the default constructs one from `creds`.
    If `quiet` is true then user-interruption messages are suppressed.
    The bucket id is resolved from `creds.buckets` when recorded there, so a least-privilege key
    without `listBuckets` works and construction makes one fewer round trip.
    '''
    self.name = bucket_name
    self.quiet = quiet
    self.client = client if client is not None else B2Client(creds.key_id, creds.key_secret)
    try:
      self.client.authorize()
      bucket_id = creds.buckets.get(bucket_name) or None # An empty id counts as unrecorded.
      if bucket_id is None:
        bucket_id = self.client.get_bucket_by_name(bucket_name).id
    except B2Unauthorized:
      exit(f'Unauthorized: invalid B2 credentials{f": {creds_desc!r}" if creds_desc else ""}.')
    self.bucket_id = bucket_id


  @classmethod
  def from_creds_path(cls, creds_path:str, bucket_name:str) -> 'B2BackupStore':
    return cls(B2Creds.load(creds_path), bucket_name, creds_desc=creds_path)


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
        self.client.download_file_by_id(version.key, dst_path, progress=progress)
      return True
    except KeyboardInterrupt:
      if not self.quiet: logI('Download interrupted by user.')
      return False



def stored_version_for_b2(fv:B2FileVersion, *, obj_key:str) -> StoredVersion:
  return StoredVersion(key=fv.file_id, obj_key=obj_key, size=fv.content_length, sha1=fv.sha1, uploaded_at=fv.uploaded_at)
