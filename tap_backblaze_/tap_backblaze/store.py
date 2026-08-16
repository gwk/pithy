# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from b2sdk._internal.exception import Unauthorized
from b2sdk.v3 import B2Api, Bucket, DownloadedFile, FileVersion, InMemoryAccountInfo
from pithy.date import DateTime
from pithy.logs import logI
from pithy.sqlite.backup import StoredVersion
from pithy.tz import tz_utc

from .creds import B2Creds
from .progress import ProgressListener


class B2BackupStore:
  '''
  Backblaze B2 implementation of the `pithy.sqlite.backup.BackupStore` protocol.
  Version history is provided by B2 file versioning: uploads to the same object key accumulate versions.
  '''

  def __init__(self, creds:B2Creds, bucket_name:str, *, creds_desc:str='') -> None:
    '`creds_desc` names the credential origin (e.g. a file path) for error messages.'
    self.name = bucket_name
    api = B2Api(InMemoryAccountInfo()) # type: ignore[no-untyped-call]
    try: api.authorize_account(application_key_id=creds.key_id, application_key=creds.key_secret.val)
    except Unauthorized:
      exit(f'Unauthorized: invalid B2 credentials{f": {creds_desc!r}" if creds_desc else ""}.')
    self.bucket:Bucket = api.get_bucket_by_name(bucket_name)


  @classmethod
  def from_creds_path(cls, creds_path:str, bucket_name:str) -> 'B2BackupStore':
    return cls(B2Creds.load(creds_path), bucket_name, creds_desc=creds_path)


  def upload(self, path:str, obj_key:str) -> bool:
    try:
      with ProgressListener('Upload progress') as progress_listener:
        self.bucket.upload_local_file(local_file=path, file_name=obj_key, progress_listener=progress_listener)
      return True
    except KeyboardInterrupt:
      logI('Upload interrupted by user.')
      return False


  def list_versions(self, obj_key:str) -> list[StoredVersion]:
    return [stored_version_for_b2(fv, obj_key=obj_key) for fv, _folder_name in self.bucket.ls(obj_key, latest_only=False)]


  def download(self, version:StoredVersion, dst_path:str) -> bool:
    try:
      with ProgressListener('Download progress') as progress_listener:
        downloaded:DownloadedFile = self.bucket.download_file_by_id(file_id=version.key, progress_listener=progress_listener)
        with open(dst_path, 'wb') as f:
          downloaded.save(f)
      return True
    except KeyboardInterrupt:
      logI('Download interrupted by user.')
      return False



def stored_version_for_b2(fv:FileVersion, *, obj_key:str) -> StoredVersion:
  sha1 = fv.get_content_sha1()
  if not isinstance(sha1, str) or sha1 == 'none': sha1 = None
  return StoredVersion(key=fv.id_, obj_key=obj_key, size=fv.size, sha1=sha1,
    uploaded_at=DateTime.fromtimestamp(fv.upload_timestamp/1000, tz=tz_utc))
