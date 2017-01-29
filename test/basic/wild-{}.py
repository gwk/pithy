#!/usr/bin/env python3

from os import environ
from sys import *

_, arg = argv

env_val = environ['TEST_WILD']
if arg == '':
  assert env_val == 'env: wild-'
elif arg == 'iot':
  assert env_val == 'env: wild-iot'
else:
  assert env_val == 'env: wild-{}'

out = 'out: wild-{}'
err = 'err: wild-{}'

if arg == 'out':
  out = 'out: wild-out'
elif arg == 'err':
  err = 'err: wild-err'

print(out, file=stdout)
print(err, file=stderr)

if arg == 'iot': exit(1)
