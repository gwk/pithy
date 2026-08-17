# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import path
from tempfile import TemporaryDirectory

from pithy.frozendicts import frozendict
from pithy.secrets import SecretStr
from tap_backblaze.api.types import B2CreatedApplicationKey
from tap_backblaze.creds import B2Creds
from utest import utest, utest_exc, utest_val


def mk_creds(**overrides:object) -> B2Creds:
  kwargs:dict = dict(key_name='backup-key', key_id='0022ab34cd56', key_secret=SecretStr('K002abc/DEF+ghi='),
    buckets=frozendict({'my-bucket': 'bkt1'}), capabilities=('listFiles', 'readFiles'))
  kwargs.update(overrides)
  return B2Creds(**kwargs)


# Validation of key id and secret.

creds = mk_creds()
utest_val('0022ab34cd56', creds.key_id, 'key_id')
utest_exc(ValueError, mk_creds, key_id='not hex!')
utest_exc(ValueError, mk_creds, key_id='')
utest_exc(ValueError, mk_creds, key_secret=SecretStr('bad secret with spaces'))
utest_exc(ValueError, mk_creds, key_secret=SecretStr(''))


# as_dict, save and load round trip.

utest({'key_name': 'backup-key', 'key_id': '0022ab34cd56', 'key_secret': 'K002abc/DEF+ghi=',
  'buckets': {'my-bucket': 'bkt1'}, 'capabilities': ['listFiles', 'readFiles']}, creds.as_dict)

with TemporaryDirectory() as tmp:
  creds_path = path.join(tmp, 'creds.json')
  creds.save(creds_path)
  utest(creds, B2Creds.load, creds_path)


# from_created_key.

created = B2CreatedApplicationKey(key_id='0022ab34cd56', key_name='backup-key', account_id='acct',
  capabilities=('readFiles', 'listFiles'), bucket_ids=('bkt1',), name_prefix=None, expiration_timestamp=None,
  application_key=SecretStr('K002abc/DEF+ghi='))
from_key = B2Creds.from_created_key(created, {'my-bucket': 'bkt1'})
utest_val(creds, from_key, 'from_created_key equals directly constructed creds') # Capabilities are sorted.
utest_val(('listFiles', 'readFiles'), from_key.capabilities, 'capabilities sorted')
