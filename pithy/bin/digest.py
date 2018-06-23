#!/usr/bin/env python3
# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'print file hashes. first argument is the format; remaining args are the paths.'

import base64
import hashlib
from pithy.io import errSL
from pithy.string import le32
from sys import argv, stderr


hash_classes = {
  '1'   : hashlib.sha1,
  '224' : hashlib.sha224,
  '256' : hashlib.sha256,
  '384' : hashlib.sha384,
  '512' : hashlib.sha512,
  'md5' : hashlib.md5,
}


def main():
  hash_name = argv[1]
  in_paths = argv[2:]

  try:
    hash_class = hash_classes[hash_name]
  except KeyError:
    errSL('invalid hash name:', hash_name)
    errSL('available hash functions:', *hash_classes)
    exit(1)

  path_width = min(64, max(len(p) for p in in_paths))

  for path in in_paths:
    digest(hash_class, path, path_width)


def digest(hash_class, path, path_width):
  hash_chunk_size = 1 << 16
  #^ a quick timing experiment suggested that chunk sizes larger than this are not faster.
  try: f = open(path, 'rb')
  except IsADirectoryError: exit(f'expected a file but found a directory: {path}')
  h = hash_class()
  while True:
    chunk = f.read(hash_chunk_size)
    if not chunk: break
    h.update(chunk)

  d = h.digest()
  d16 = base64.b16encode(d).decode()
  d32 = le32(d)
  d64 = base64.urlsafe_b64encode(d).decode()
  print(f'{path:{path_width}} b16:{d16} le32:{d32} b64:{d64}')


if __name__ == '__main__': main()
