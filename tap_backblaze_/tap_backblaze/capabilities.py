# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# The complete capability vocabulary, per https://www.backblaze.com/apidocs/b2-create-key.
all_capabilities:tuple[str,...] = (
  'listKeys',
  'writeKeys',
  'deleteKeys',
  'listBuckets',
  'listAllBucketNames',
  'readBuckets',
  'writeBuckets',
  'deleteBuckets',
  'readBucketEncryption',
  'writeBucketEncryption',
  'readBucketRetentions',
  'writeBucketRetentions',
  'readFileRetentions',
  'writeFileRetentions',
  'readFileLegalHolds',
  'writeFileLegalHolds',
  'readBucketReplications',
  'writeBucketReplications',
  'bypassGovernance',
  'listFiles',
  'readFiles',
  'shareFiles',
  'writeFiles',
  'deleteFiles',
  'readBucketNotifications',
  'writeBucketNotifications',
)

all_capabilities_and_groups = all_capabilities + ('file-ro', 'file-rw', 'file-rwd')

key_mgmt_capabilities:tuple[str, ...] = ('listKeys', 'writeKeys', 'deleteKeys')

file_ro_capabilities:tuple[str, ...] = ('listFiles', 'readFiles')
file_rw_capabilities:tuple[str, ...] = tuple(file_ro_capabilities + ('writeFiles',))
file_rwd_capabilities:tuple[str, ...] = tuple(file_rw_capabilities + ('deleteFiles',))
