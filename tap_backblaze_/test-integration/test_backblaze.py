#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Integration test suite for `tap_backblaze` against the real B2 service.
Requires credentials; see readme.md. Run with `just test-backblaze`.

The suite takes two credential files: a read-only key and a read-write key.
Uploads and cleanup use the read-write key; every listing and download uses the read-only key.
This mirrors our practice, where developers and test servers can restore from backups but cannot write them.

Every object is written under a unique per-run prefix, so concurrent or repeated runs cannot collide,
and the run deletes every version it created on the way out, including on failure.
'''

from argparse import Namespace
from hashlib import sha1
from os import getpid, path, urandom
from tempfile import TemporaryDirectory
from time import time
from traceback import print_exc

from pithy.argparser import ArgParser
from pithy.filestatus import path_exists
from pithy.frozendicts import frozendict
from pithy.secrets import SecretStr
from pithy.sqlite import Conn
from requests import RequestException
from tap_backblaze.api import B2Client, B2Error, B2NotFound, B2Unauthorized
from tap_backblaze.creds import B2Creds
from tap_backblaze.store import B2BackupStore, stored_version_for_b2


required_ro_capabilities = frozenset({'listFiles', 'readFiles'})
required_rw_capabilities = frozenset({'listFiles', 'readFiles', 'writeFiles', 'deleteFiles'})

# Capabilities that the read-only key must not have; the separation of duties is what this suite verifies.
forbidden_ro_capabilities = frozenset({'writeFiles', 'deleteFiles'})


class TestRun:
  'Holds the two clients, tracks results, and records every uploaded version for cleanup.'

  def __init__(self, *, ro_creds:B2Creds, ro_client:B2Client, rw_creds:B2Creds, rw_client:B2Client,
   bucket_name:str, ro_bucket_id:str, rw_bucket_id:str, tmp_dir:str) -> None:
    self.ro_creds = ro_creds
    self.ro_client = ro_client
    self.rw_creds = rw_creds
    self.rw_client = rw_client
    self.bucket_name = bucket_name
    self.ro_bucket_id = ro_bucket_id
    self.rw_bucket_id = rw_bucket_id
    self.tmp_dir = tmp_dir
    self.prefix = f'test-integration/{int(time())}-{getpid()}/'
    self.obj_keys:set[str] = set()
    self.failures:list[str] = []
    self.passes = 0

  def obj_key(self, name:str) -> str:
    key = self.prefix + name
    self.obj_keys.add(key)
    return key

  def tmp_path(self, name:str) -> str: return path.join(self.tmp_dir, name)

  def check(self, label:str, ok:bool, detail:str='') -> None:
    if ok:
      self.passes += 1
      print(f'  ok: {label}')
    else:
      self.failures.append(label)
      print(f'  FAIL: {label}{f": {detail}" if detail else ""}')

  def cleanup(self) -> None:
    'Delete every version of every object key this run created, using the read-write key.'
    for obj_key in sorted(self.obj_keys):
      try:
        for fv in list(self.rw_client.list_file_versions(self.rw_bucket_id, obj_key)):
          self.rw_client.delete_file_version(fv.file_id, fv.file_name)
          print(f'  cleaned up: {fv.file_name} ({fv.file_id})')
      except Exception:
        print(f'  cleanup failed for {obj_key!r}:')
        print_exc()


def main() -> None:
  parser = ArgParser(description='Integration test suite for tap_backblaze against the real B2 service.')
  parser.add_argument('ro_creds', help='Path to the read-only B2 credentials JSON file.')
  parser.add_argument('rw_creds', help='Path to the read-write B2 credentials JSON file.')
  parser.add_argument('-bucket', help='Name of the test bucket; defaults to the sole bucket recorded in the credentials.')
  args = parser.parse_args()

  with TemporaryDirectory() as tmp_dir:
    run = preflight(args, tmp_dir)
    try:
      test_setup(run)
      test_small_file(run)
      test_versioning(run)
      test_large_file(run)
      test_backup_store(run)
      test_read_only_enforcement(run)
      test_error_paths(run)
      test_keys_optional(run)
    except BaseException:
      print('aborted:')
      print_exc()
      run.failures.append('run aborted by exception')
    finally:
      print('cleanup:')
      run.cleanup()

  print(f'passed: {run.passes}; failed: {len(run.failures)}')
  if run.failures: exit(1)


def preflight(args:Namespace, tmp_dir:str) -> TestRun:
  '''
  Load both keys, authorize them, and resolve the bucket.
  Everything here is fatal misconfiguration rather than a test failure;
  in particular the run must not upload anything before it knows that cleanup can delete it.
  '''
  ro_creds, ro_client = load_client(args.ro_creds, 'read-only')
  rw_creds, rw_client = load_client(args.rw_creds, 'read-write')
  require_capabilities(ro_client, required_ro_capabilities, args.ro_creds, 'read-only')
  require_capabilities(rw_client, required_rw_capabilities, args.rw_creds, 'read-write')

  bucket_name = args.bucket or sole_bucket_name(rw_creds, args.rw_creds, 'read-write')
  ro_bucket_id = resolve_bucket_id(ro_client, ro_creds, bucket_name, 'read-only')
  rw_bucket_id = resolve_bucket_id(rw_client, rw_creds, bucket_name, 'read-write')

  return TestRun(ro_creds=ro_creds, ro_client=ro_client, rw_creds=rw_creds, rw_client=rw_client,
    bucket_name=bucket_name, ro_bucket_id=ro_bucket_id, rw_bucket_id=rw_bucket_id, tmp_dir=tmp_dir)


def load_client(creds_path:str, desc:str) -> tuple[B2Creds,B2Client]:
  'Load credentials and authorize a client, exiting with a clear message on any configuration problem.'
  if not path_exists(creds_path, follow=True):
    exit(f'error: the {desc} credentials path does not exist: {creds_path!r}.')
  creds = B2Creds.load(creds_path)
  client = B2Client(creds.key_id, creds.key_secret)
  try: client.authorize()
  except B2Unauthorized as e:
    exit(f'error: the {desc} credentials were rejected: {creds_path!r}; {e}')
  except RequestException as e:
    exit(f'error: could not reach the B2 service to authorize the {desc} key: {e}')
  return creds, client


def require_capabilities(client:B2Client, required:frozenset[str], creds_path:str, desc:str) -> None:
  '''
  Verify the capabilities that the service reports for the key, which are authoritative;
  the capabilities recorded in the creds file are only a copy made at creation.
  '''
  missing = required - set(client.auth.capabilities)
  if missing:
    exit(f'error: the {desc} key lacks required capabilities {sorted(missing)}: {creds_path!r}.\n'
      'Recreate it with `python -m tap_backblaze.key create`; see readme.md for the required capabilities.')


def sole_bucket_name(creds:B2Creds, creds_path:str, desc:str) -> str:
  names = sorted(creds.buckets)
  if len(names) != 1:
    exit(f'error: the {desc} credentials record {len(names)} buckets; pass -bucket to choose one: {creds_path!r}.')
  return names[0]


def resolve_bucket_id(client:B2Client, creds:B2Creds, bucket_name:str, desc:str) -> str:
  '''
  Resolve the test bucket id without requiring the `listBuckets` capability:
  from the creds mapping, else from the authorize response's allowed buckets, else by `b2_list_buckets`.
  '''
  recorded = creds.buckets.get(bucket_name) or None # An empty id counts as unrecorded.
  if recorded is not None: return recorded
  auth = client.auth
  allowed = {b.name: b.id for b in auth.allowed_buckets if b.name is not None}
  if bucket_name in allowed: return allowed[bucket_name]
  if 'listBuckets' not in auth.capabilities:
    exit(f'error: cannot resolve bucket {bucket_name!r} for the {desc} key: '
      'the creds record no bucket id, the key allows no matching bucket, and the key lacks listBuckets.')
  return client.get_bucket_by_name(bucket_name).id


def test_setup(run:TestRun) -> None:
  'Check the shape of both authorizations and the separation of duties between the two keys.'
  print('setup:')
  ro_auth = run.ro_client.auth
  rw_auth = run.rw_client.auth

  granted = forbidden_ro_capabilities & set(ro_auth.capabilities)
  run.check('read-only key cannot write or delete', not granted, f'granted: {sorted(granted)}')
  run.check('both keys resolve the same bucket id', run.ro_bucket_id == run.rw_bucket_id,
    f'{run.ro_bucket_id} != {run.rw_bucket_id}')
  run.check('both keys are for the same account', ro_auth.account_id == rw_auth.account_id,
    f'{ro_auth.account_id} != {rw_auth.account_id}')

  run.check('part sizes are sane', 0 < rw_auth.absolute_minimum_part_size <= rw_auth.recommended_part_size,
    f'absolute min {rw_auth.absolute_minimum_part_size}; recommended {rw_auth.recommended_part_size}')
  run.check('api url', rw_auth.api_url.startswith('https://'), rw_auth.api_url)
  run.check('download url', ro_auth.download_url.startswith('https://'), ro_auth.download_url)


def test_small_file(run:TestRun) -> None:
  print('small file:')
  content = urandom(64 * 1024)
  src = run.tmp_path('small.bin')
  with open(src, 'wb') as f: f.write(content)
  obj_key = run.obj_key('small.bin')

  fv = run.rw_client.upload_file(run.rw_bucket_id, src, obj_key)
  run.check('upload sha1', fv.sha1 == sha1(content).hexdigest(), repr(fv.sha1))
  run.check('upload size', fv.content_length == len(content), str(fv.content_length))

  versions = list(run.ro_client.list_file_versions(run.ro_bucket_id, obj_key))
  run.check('one version listed by the read-only key', len(versions) == 1, str(len(versions)))
  run.check('listed version id', bool(versions) and versions[0].file_id == fv.file_id)

  dst = run.tmp_path('small_dl.bin')
  run.ro_client.download_file_by_id(fv.file_id, dst)
  with open(dst, 'rb') as f: downloaded = f.read()
  run.check('download bytes match', downloaded == content)
  run.check('download sha1 matches', sha1(downloaded).hexdigest() == fv.sha1)


def test_versioning(run:TestRun) -> None:
  print('versioning:')
  obj_key = run.obj_key('versioned.bin')
  contents = [b'first version content', b'second version content, longer']
  ids = []
  for i, content in enumerate(contents):
    src = run.tmp_path(f'versioned{i}.bin')
    with open(src, 'wb') as f: f.write(content)
    ids.append(run.rw_client.upload_file(run.rw_bucket_id, src, obj_key).file_id)

  versions = list(run.ro_client.list_file_versions(run.ro_bucket_id, obj_key))
  run.check('two versions', len(versions) == 2, str(len(versions)))
  by_time = sorted(versions, key=lambda v: v.uploaded_at)
  run.check('ordering by uploaded_at', [v.file_id for v in by_time] == ids,
    f'{[v.file_id for v in by_time]} != {ids}')

  dst = run.tmp_path('versioned_older.bin')
  run.ro_client.download_file_by_id(ids[0], dst)
  with open(dst, 'rb') as f:
    run.check('older version content', f.read() == contents[0])


def test_large_file(run:TestRun) -> None:
  print('large file:')
  part_size = run.rw_client.auth.absolute_minimum_part_size
  content = urandom(part_size * 2) # Two parts at the absolute minimum part size.
  digest = sha1(content).hexdigest()
  src = run.tmp_path('large.bin')
  with open(src, 'wb') as f: f.write(content)
  obj_key = run.obj_key('large.bin')

  fv = run.rw_client.upload_file(run.rw_bucket_id, src, obj_key, part_size=part_size)
  run.check('contentSha1 is "none"', fv.content_sha1 == 'none', repr(fv.content_sha1))
  run.check('large_file_sha1 file info', fv.file_info.get('large_file_sha1') == digest, repr(fv.file_info))
  run.check('sha1 property is the true digest', fv.sha1 == digest, repr(fv.sha1))
  sv = stored_version_for_b2(fv, obj_key=obj_key)
  run.check('StoredVersion.sha1 is the true digest', sv.sha1 == digest, repr(sv.sha1))

  dst = run.tmp_path('large_dl.bin')
  run.ro_client.download_file_by_id(fv.file_id, dst)
  with open(dst, 'rb') as f:
    run.check('large download bytes match', f.read() == content)


def test_backup_store(run:TestRun) -> None:
  '''
  A B2BackupStore round trip with a real SQLite file: the case the dependent application depends on.
  The backup is written by a read-write store and restored by a read-only store, as in production.
  '''
  print('backup store round trip:')
  db_path = run.tmp_path('store.db')
  with Conn(db_path, mode='rwc').closing() as conn:
    with conn: # The Conn runs in autocommit mode; using it as a context manager runs an explicit transaction.
      c = conn.cursor()
      c.run('CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)')
      c.run("INSERT INTO t (val) VALUES ('backup store test row')")
  with open(db_path, 'rb') as f: db_bytes = f.read()

  # Record the resolved bucket ids in the creds, exercising the no-listBuckets construction path.
  rw_store = B2BackupStore(creds_with_bucket(run.rw_creds, run.bucket_name, run.rw_bucket_id), run.bucket_name,
    client=run.rw_client)
  ro_store = B2BackupStore(creds_with_bucket(run.ro_creds, run.bucket_name, run.ro_bucket_id), run.bucket_name,
    client=run.ro_client)

  obj_key = run.obj_key('store.db')
  run.check('store.upload', rw_store.upload(db_path, obj_key))

  versions = ro_store.list_versions(obj_key)
  run.check('store.list_versions', len(versions) == 1, str(len(versions)))
  run.check('stored sha1', bool(versions) and versions[0].sha1 == sha1(db_bytes).hexdigest())

  dst = run.tmp_path('store_dl.db')
  run.check('store.download', bool(versions) and ro_store.download(versions[0], dst))
  with open(dst, 'rb') as f:
    run.check('restored bytes match', f.read() == db_bytes)
  with Conn(dst, mode='ro').closing() as conn:
    row = conn.cursor().run('SELECT val FROM t').one_col()
    run.check('restored database row', row == 'backup store test row', repr(row))


def test_read_only_enforcement(run:TestRun) -> None:
  'The read-only key must be refused by the service for writes, not merely by our own code.'
  print('read-only enforcement:')
  src = run.tmp_path('denied.bin')
  with open(src, 'wb') as f: f.write(b'this upload must be refused')
  obj_key = run.obj_key('denied.bin') # Recorded for cleanup in case the service unexpectedly accepts it.

  try:
    run.ro_client.upload_file(run.ro_bucket_id, src, obj_key)
    run.check('read-only upload raises B2Unauthorized', False, 'the upload succeeded')
  except B2Error as e:
    run.check('read-only upload raises B2Unauthorized', isinstance(e, B2Unauthorized), str(e))

  versions = list(run.ro_client.list_file_versions(run.ro_bucket_id, run.prefix + 'small.bin'))
  if not versions:
    run.check('read-only delete raises B2Unauthorized', False, 'no version was available to attempt deleting')
    return
  fv = versions[0]
  try:
    run.ro_client.delete_file_version(fv.file_id, fv.file_name)
    run.check('read-only delete raises B2Unauthorized', False, 'the delete succeeded')
  except B2Error as e:
    run.check('read-only delete raises B2Unauthorized', isinstance(e, B2Unauthorized), str(e))


def test_error_paths(run:TestRun) -> None:
  print('error paths:')
  # A file id that once existed and was deleted: the restore case where the chosen version is gone.
  # This has to be a real id; B2 answers 400 bad_request for a synthetic id that does not parse against a real bucket.
  src = run.tmp_path('deleted.bin')
  with open(src, 'wb') as f: f.write(b'this version is deleted before it is downloaded')
  obj_key = run.obj_key('deleted.bin')
  fv = run.rw_client.upload_file(run.rw_bucket_id, src, obj_key)
  run.rw_client.delete_file_version(fv.file_id, fv.file_name)
  try:
    run.ro_client.download_file_by_id(fv.file_id, run.tmp_path('deleted_dl.bin'))
    run.check('deleted file id raises B2NotFound', False, 'no exception raised')
  except B2Error as e:
    run.check('deleted file id raises B2NotFound', isinstance(e, B2NotFound), str(e))

  try:
    run.ro_client.download_file_by_id('4_z0000000000000000000000_f000000000000000_d20260101_m000000_c000_v0000000_t0000',
      run.tmp_path('malformed.bin'))
    run.check('malformed file id raises B2Error', False, 'no exception raised')
  except B2Error as e:
    run.check('malformed file id raises B2Error', e.status == 400, str(e))

  bad_client = B2Client(run.ro_creds.key_id, SecretStr('K000badBadBad0000000000000000000'))
  try:
    bad_client.authorize()
    run.check('wrong secret raises B2Unauthorized', False, 'no exception raised')
  except B2Unauthorized:
    run.check('wrong secret raises B2Unauthorized', True)


def test_keys_optional(run:TestRun) -> None:
  'Key management checks, skipped when the read-write key lacks the listKeys/writeKeys capabilities.'
  print('keys (optional):')
  capabilities = set(run.rw_client.auth.capabilities)
  if 'listKeys' not in capabilities:
    print('  skipped: the read-write key lacks listKeys.')
    return
  keys = run.rw_client.list_keys()
  run.check('list_keys includes both test keys',
    {run.ro_creds.key_id, run.rw_creds.key_id} <= {k.key_id for k in keys}, str(len(keys)))

  if 'writeKeys' not in capabilities:
    print('  skipped: the read-write key lacks writeKeys.')
    return
  created = run.rw_client.create_key(f'throwaway-{getpid()}', ['listFiles'], [run.rw_bucket_id],
    valid_duration_seconds=3600)
  run.check('create_key returns a secret', bool(created.application_key.val))
  run.rw_client.delete_key(created.key_id)
  remaining = {k.key_id for k in run.rw_client.list_keys()}
  run.check('throwaway key deleted', created.key_id not in remaining)


def creds_with_bucket(creds:B2Creds, bucket_name:str, bucket_id:str) -> B2Creds:
  'Copy the credentials with the resolved bucket id recorded, so B2BackupStore need not call listBuckets.'
  return B2Creds(key_name=creds.key_name, key_id=creds.key_id, key_secret=creds.key_secret,
    buckets=frozendict({bucket_name: bucket_id}), capabilities=creds.capabilities)


if __name__ == '__main__': main()
