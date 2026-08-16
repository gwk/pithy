# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.json import JsonDict, out_json


key_remap = {
  'keyID': 'key_id',
  'applicationKey': 'key_secret',
  'keyName': 'key_name',
  'bucketName': 'bucket_name',
}


def parse_backblaze_application_key_text(val:str) -> JsonDict:
  '''
  Application key text copied from the backblaze website looks like this:

  ```
  keyID:
  0000000000000000000000001
  applicationKey:
  XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
  keyName:
  SOME-KEY-NAME
  bucketName:
  SOME-BUCKET-NAME
  capabilities:
  deleteFiles, ...
  expiration:
  -
  namePrefix:
  (none)
  ```

  This function parses that text into a JSON dictionary.
  '''

  lines = val.strip().splitlines()
  keys = lines[0::2]
  vals = lines[1::2]

  if len(keys) != len(vals):
    raise ValueError('Mismatched number of key and value lines in backblaze application key text.')

  result:JsonDict = {}
  for k, v in zip(keys, vals, strict=True):
    k = k.strip()
    if not k.endswith(':'):
      raise ValueError(f'Invalid backblaze application key text: expected key line to end with colon: {k!r}')
    k = k[:-1]
    v = v.strip()
    if v in ('-', '(none)'): v = ''
    result[key_remap.get(k, k)] = v

  return result


def main() -> None:
  from sys import stdin
  input_text = stdin.read()
  creds = parse_backblaze_application_key_text(input_text)
  out_json(creds)


if __name__ == '__main__': main()
