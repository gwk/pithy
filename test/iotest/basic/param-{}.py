#!/usr/bin/env python3

from os import environ
from sys import argv, stderr, stdout

_, arg = argv

env_val = environ['TEST_PARAM']
if arg == '':
  assert env_val == 'env: param-'
elif arg == 'ARG': # arg value specified by param-arg.iot args, overriding format match.
  assert env_val == 'env: param-arg'
elif arg == 'iot':
  assert env_val == 'env: param-iot'
else:
  assert env_val == 'env: param-{}'

out = 'out: param-{}'
err = 'err: param-{}'

if arg == 'out':
  out = 'out: param-out'
elif arg == 'err':
  err = 'err: param-err'

print(out, file=stdout)
print(err, file=stderr)
