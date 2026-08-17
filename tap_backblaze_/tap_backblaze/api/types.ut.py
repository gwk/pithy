# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.date import DateTime
from pithy.frozendicts import frozendict
from pithy.json import JsonDict
from pithy.tz import tz_utc
from tap_backblaze.api.types import (B2AllowedBucket, B2ApplicationKey, B2Auth, B2Bucket, B2CreatedApplicationKey,
  B2FileVersion, B2ParseError, B2UploadUrl)
from utest import utest_exc, utest_val


# A recorded (anonymized) v4 b2_authorize_account response.
authorize_response:JsonDict = {
  'accountId': 'acct0123',
  'authorizationToken': '4_token',
  'apiInfo': {
    'groupsApi': {},
    'storageApi': {
      'apiUrl': 'https://api001.backblazeb2.com',
      'downloadUrl': 'https://f001.backblazeb2.com',
      's3ApiUrl': 'https://s3.us-west-001.backblazeb2.com',
      'recommendedPartSize': 100_000_000,
      'absoluteMinimumPartSize': 5_000_000,
      'capabilities': ['listFiles', 'readFiles', 'writeFiles'],
      'namePrefix': None,
      'allowed': {
        'buckets': [{'id': 'bkt1', 'name': 'my-bucket'}],
        'capabilities': ['listFiles', 'readFiles', 'writeFiles'],
        'namePrefix': None,
      },
    },
  },
}

auth = B2Auth.from_json(authorize_response)
utest_val('acct0123', auth.account_id, 'account_id')
utest_val('4_token', auth.auth_token.val, 'auth_token')
utest_val('https://api001.backblazeb2.com', auth.api_url, 'api_url')
utest_val('https://f001.backblazeb2.com', auth.download_url, 'download_url')
utest_val(100_000_000, auth.recommended_part_size, 'recommended_part_size')
utest_val(5_000_000, auth.absolute_minimum_part_size, 'absolute_minimum_part_size')
utest_val(('listFiles', 'readFiles', 'writeFiles'), auth.capabilities, 'capabilities')
utest_val((B2AllowedBucket(id='bkt1', name='my-bucket'),), auth.allowed_buckets, 'allowed_buckets')
utest_val(None, auth.allowed_name_prefix, 'allowed_name_prefix')

# An unrestricted key has no buckets list; a deleted or unlistable bucket has a null name.
unrestricted:JsonDict = {
  'accountId': 'a', 'authorizationToken': 't',
  'apiInfo': {'storageApi': {
    'apiUrl': 'u', 'downloadUrl': 'd', 'recommendedPartSize': 100, 'absoluteMinimumPartSize': 5,
    'allowed': {'buckets': None, 'capabilities': ['listKeys'], 'namePrefix': None}}},
}
auth = B2Auth.from_json(unrestricted)
utest_val((), auth.allowed_buckets, 'unrestricted allowed_buckets')

utest_exc(B2ParseError, B2Auth.from_json, {'accountId': 'a'}) # Missing authorizationToken and apiInfo.
utest_exc(B2ParseError, B2Auth.from_json,
  {'accountId': 'a', 'authorizationToken': 't', 'apiInfo': {'storageApi': {
    'apiUrl': 'u', 'downloadUrl': 'd', 'recommendedPartSize': 'big', 'absoluteMinimumPartSize': 5,
    'allowed': {'capabilities': [], 'namePrefix': None}}}}) # recommendedPartSize is not an integer.


# Bucket parsing.

bucket = B2Bucket.from_json({'bucketId': 'bkt1', 'bucketName': 'my-bucket', 'bucketType': 'allPrivate',
  'accountId': 'acct0123', 'unexpectedExtra': True}) # Unknown keys are tolerated for forward compatibility.
utest_val('bkt1', bucket.id, 'bucket id')
utest_val('my-bucket', bucket.name, 'bucket name')
utest_val('allPrivate', bucket.type, 'bucket type')
utest_val('acct0123', bucket.account_id, 'bucket account_id')

utest_exc(B2ParseError, B2Bucket.from_json, {'bucketId': 'bkt1'}) # Missing fields raise.


# File version parsing: a small file.

small = B2FileVersion.from_json({
  'fileId': '4_id_small', 'fileName': 'db/main.db', 'action': 'upload', 'contentLength': 1024,
  'contentSha1': 'a'*40, 'contentType': 'application/octet-stream', 'fileInfo': {},
  'uploadTimestamp': 1_755_000_000_000})
utest_val('a'*40, small.sha1, 'small sha1')
utest_val(DateTime.fromtimestamp(1_755_000_000, tz=tz_utc), small.uploaded_at, 'uploaded_at')

# A large file: contentSha1 is "none" and the digest falls back to fileInfo.large_file_sha1.
large = B2FileVersion.from_json({
  'fileId': '4_id_large', 'fileName': 'db/main.db', 'action': 'upload', 'contentLength': 10_000_000,
  'contentSha1': 'none', 'fileInfo': {'large_file_sha1': 'b'*40}, 'uploadTimestamp': 1_755_000_000_000})
utest_val('b'*40, large.sha1, 'large sha1 fallback')
utest_val(frozendict({'large_file_sha1': 'b'*40}), large.file_info, 'file_info')

# Neither digest is present: sha1 is None.
no_sha = B2FileVersion.from_json({
  'fileId': 'i', 'fileName': 'n', 'action': 'upload', 'contentLength': 1, 'contentSha1': 'none',
  'fileInfo': {}, 'uploadTimestamp': 0})
utest_val(None, no_sha.sha1, 'absent sha1')

# An "unverified:" prefix is stripped.
unverified = B2FileVersion.from_json({
  'fileId': 'i', 'fileName': 'n', 'action': 'upload', 'contentLength': 1, 'contentSha1': f'unverified:{"c"*40}',
  'fileInfo': {}, 'uploadTimestamp': 0})
utest_val('c'*40, unverified.sha1, 'unverified sha1')

# An upload response omits the action; it defaults to "upload".
uploaded = B2FileVersion.from_json({
  'fileId': 'i', 'fileName': 'n', 'contentLength': 1, 'contentSha1': 'd'*40, 'uploadTimestamp': 0})
utest_val('upload', uploaded.action, 'default action')

utest_exc(B2ParseError, B2FileVersion.from_json, {'fileId': 'i', 'fileName': 'n'}) # Missing contentLength raises.
utest_exc(B2ParseError, B2FileVersion.from_json, {'fileId': 'i', 'fileName': 'n', 'contentLength': 'x',
  'uploadTimestamp': 0}) # Mistyped contentLength raises.


# Upload URL parsing.

upload_url = B2UploadUrl.from_json({'bucketId': 'b', 'uploadUrl': 'https://pod.backblazeb2.com/u', 'authorizationToken': 'ut'})
utest_val('https://pod.backblazeb2.com/u', upload_url.url, 'upload url')
utest_val('ut', upload_url.auth_token.val, 'upload auth token')


# Application key parsing.

key = B2ApplicationKey.from_json({'applicationKeyId': 'kid', 'keyName': 'kn', 'accountId': 'a',
  'capabilities': ['listFiles'], 'bucketIds': ['b1', 'b2'], 'namePrefix': None})
utest_val('kid', key.key_id, 'key_id')
utest_val(('b1', 'b2'), key.bucket_ids, 'bucket_ids')
utest_val(None, key.expiration_timestamp, 'expiration_timestamp')

# An unrestricted key omits bucketIds.
key = B2ApplicationKey.from_json({'applicationKeyId': 'kid', 'keyName': 'kn', 'accountId': 'a', 'capabilities': []})
utest_val((), key.bucket_ids, 'unrestricted bucket_ids')

created = B2CreatedApplicationKey.from_json({'applicationKeyId': 'kid', 'keyName': 'kn', 'accountId': 'a',
  'capabilities': ['listFiles'], 'bucketIds': ['b1'], 'applicationKey': 'SECRET'})
utest_val('SECRET', created.application_key.val, 'created key secret')
utest_val('SecretStr(*)', repr(created.application_key), 'created key secret repr')

utest_exc(B2ParseError, B2CreatedApplicationKey.from_json, {'applicationKeyId': 'kid', 'keyName': 'kn', 'accountId': 'a',
  'capabilities': []}) # Missing applicationKey raises.
