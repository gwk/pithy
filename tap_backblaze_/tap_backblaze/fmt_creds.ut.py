# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from tap_backblaze.fmt_creds import parse_backblaze_application_key_text
from utest import utest, utest_exc


website_text = '''
keyID:
0000000000000000000000001
applicationKey:
K000XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
keyName:
SOME-KEY-NAME
bucketName:
SOME-BUCKET-NAME
capabilities:
deleteFiles, listFiles
expiration:
-
namePrefix:
(none)
'''

utest({
  'key_id': '0000000000000000000000001',
  'key_secret': 'K000XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
  'key_name': 'SOME-KEY-NAME',
  'bucket_name': 'SOME-BUCKET-NAME',
  'capabilities': 'deleteFiles, listFiles',
  'expiration': '',
  'namePrefix': '',
}, parse_backblaze_application_key_text, website_text)

# Unknown keys pass through unmapped.
utest({'someFutureKey': 'v'}, parse_backblaze_application_key_text, 'someFutureKey:\nv')

# Mismatched key and value lines raise.
utest_exc(ValueError, parse_backblaze_application_key_text, 'keyID:\nvalue\ndangling:')

# A key line without a trailing colon raises.
utest_exc(ValueError, parse_backblaze_application_key_text, 'keyID\nvalue')
