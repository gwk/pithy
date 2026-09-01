# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, cast, Iterator

from pithy.date import DateTime
from pithy.frozendicts import frozendict
from pithy.secrets import SecretStr
from pithy.sqlite.backup import StoredVersion
from pithy.tz import tz_utc
from tap_backblaze.api import B2Bucket, B2Client, B2FileVersion, B2NotFound
from tap_backblaze.api.client import Progress
from tap_backblaze.creds import B2Creds
from tap_backblaze.store import B2BackupStore, stored_version_for_b2
from utest import utest, utest_exc, utest_val


def mk_version(*, file_id:str='4_fid', size:int=1024, sha:str|None='a'*40, ts:int=1_755_000_000_000) -> B2FileVersion:
  return B2FileVersion(file_id=file_id, file_name='main.db', action='upload', content_length=size, content_sha1=sha,
    file_info=frozendict(), upload_timestamp=ts)


class FakeB2Client:
  'A fake standing in for B2Client in B2BackupStore tests; records calls and follows a simple script.'

  def __init__(self, *, versions:list[B2FileVersion]|None=None, upload_exc:BaseException|None=None,
   download_exc:BaseException|None=None) -> None:
    self.versions = versions or []
    self.upload_exc = upload_exc
    self.download_exc = download_exc
    self.calls:list[tuple[str,...]] = []

  def authorize(self) -> None:
    self.calls.append(('authorize',))

  def get_bucket_by_name(self, name:str) -> B2Bucket:
    self.calls.append(('get_bucket_by_name', name))
    if name != 'known-bucket': raise B2NotFound(404, 'not_found', f'No bucket named {name!r}.')
    return B2Bucket(id='looked-up-id', name=name, type='allPrivate', account_id='acct')

  def upload_file(self, bucket_id:str, path:str, obj_key:str, *, progress:Progress|None=None, **kwargs:Any
   ) -> B2FileVersion:
    self.calls.append(('upload_file', bucket_id, path, obj_key))
    if self.upload_exc is not None: raise self.upload_exc
    return mk_version()

  def list_file_versions(self, bucket_id:str, obj_key:str) -> Iterator[B2FileVersion]:
    self.calls.append(('list_file_versions', bucket_id, obj_key))
    yield from self.versions

  def download_file_by_id(self, file_id:str, dst_path:str, *, progress:Progress|None=None) -> None:
    self.calls.append(('download_file_by_id', file_id, dst_path))
    if self.download_exc is not None: raise self.download_exc


def mk_creds(buckets:dict[str,str]|None=None) -> B2Creds:
  return B2Creds(key_name='k', key_id='00ab', key_secret=SecretStr('c2VjcmV0'), buckets=frozendict(buckets or {}))


def mk_store(fake:FakeB2Client, *, bucket_name:str='known-bucket', buckets:dict[str,str]|None=None) -> B2BackupStore:
  return B2BackupStore(mk_creds(buckets), bucket_name, client=cast(B2Client, fake), quiet=True)


# Bucket id resolution: from the creds mapping when present, making no listBuckets round trip.

fake = FakeB2Client()
store = mk_store(fake, bucket_name='any-bucket', buckets={'any-bucket': 'creds-id'})
utest_val('creds-id', store.bucket_id, 'bucket id from creds')
utest_val([('authorize',)], fake.calls, 'no bucket lookup when the creds record the id')

# Fallback lookup by name.
fake = FakeB2Client()
store = mk_store(fake)
utest_val('looked-up-id', store.bucket_id, 'bucket id from lookup')
utest_val([('authorize',), ('get_bucket_by_name', 'known-bucket')], fake.calls, 'lookup call')
utest_val('known-bucket', store.name, 'store name')


# stored_version_for_b2 mapping.

sv = stored_version_for_b2(mk_version(), obj_key='main.db')
utest_val(StoredVersion(key='4_fid', obj_key='main.db', size=1024, sha1='a'*40,
  uploaded_at=DateTime.fromtimestamp(1_755_000_000, tz=tz_utc)), sv, 'stored version mapping')

# A large file version maps its sha1 through the large_file_sha1 fallback.
large = B2FileVersion(file_id='4_l', file_name='main.db', action='upload', content_length=1, content_sha1='none',
  file_info=frozendict({'large_file_sha1': 'b'*40}), upload_timestamp=0)
utest_val('b'*40, stored_version_for_b2(large, obj_key='main.db').sha1, 'large version sha1')


# upload returns True on success, False on KeyboardInterrupt.

fake = FakeB2Client()
store = mk_store(fake)
utest(True, store.upload, '/tmp/main.db', 'main.db')
utest_val(('upload_file', 'looked-up-id', '/tmp/main.db', 'main.db'), fake.calls[-1], 'upload call')

fake = FakeB2Client(upload_exc=KeyboardInterrupt())
utest(False, mk_store(fake).upload, '/tmp/main.db', 'main.db')

# Other exceptions propagate.
fake = FakeB2Client(upload_exc=B2NotFound(404, 'not_found', 'nope'))
utest_exc(B2NotFound, mk_store(fake).upload, '/tmp/main.db', 'main.db')


# list_versions ordering and pass-through.

versions = [mk_version(file_id='f1', ts=2_000), mk_version(file_id='f2', ts=1_000)]
fake = FakeB2Client(versions=versions)
result = mk_store(fake).list_versions('main.db')
utest_val(['f1', 'f2'], [sv.key for sv in result], 'list_versions preserves client order')
utest_val(('list_file_versions', 'looked-up-id', 'main.db'), fake.calls[-1], 'list call')


# download returns True on success, False on KeyboardInterrupt.

fake = FakeB2Client()
store = mk_store(fake)
version = stored_version_for_b2(mk_version(), obj_key='main.db')
utest(True, store.download, version, '/tmp/restored.db')
utest_val(('download_file_by_id', '4_fid', '/tmp/restored.db'), fake.calls[-1], 'download call')

fake = FakeB2Client(download_exc=KeyboardInterrupt())
utest(False, mk_store(fake).download, version, '/tmp/restored.db')
