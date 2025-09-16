# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Print file hashes. The first argument is the format; remaining args are the paths.'

import hashlib
from typing import Callable

import blake3


digest_fns:dict[str,Callable] = {
  'blake2b'   : hashlib.blake2b,
  'blake2s'   : hashlib.blake2s,
  'blake3'    : blake3.blake3,
  'md5'       : hashlib.md5,
  'sha1'      : hashlib.sha1,
  'sha224'    : hashlib.sha224,
  'sha256'    : hashlib.sha256,
  'sha3_224'  : hashlib.sha3_224,
  'sha3_256'  : hashlib.sha3_256,
  'sha3_384'  : hashlib.sha3_384,
  'sha3_512'  : hashlib.sha3_512,
  'sha384'    : hashlib.sha384,
  'sha512'    : hashlib.sha512,
  'shake_128' : hashlib.shake_128,
  'shake_256' : hashlib.shake_256,
}
