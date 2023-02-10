# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'print file hashes. first argument is the format; remaining args are the paths.'

import hashlib
from argparse import ArgumentParser
from base64 import b16encode, b32encode, b64encode, urlsafe_b64encode
from typing import Any, ByteString, Callable, Dict, List, Optional, Tuple, TypeVar

import blake3
from pithy.encodings import enc_lep62, enc_lep128_to_utf8
from pithy.io import errSL


_ByteString = TypeVar('_ByteString', ByteString, bytes, bytearray, memoryview) # Hack around the typeshed defs from base64.
_Encoder = Callable[[_ByteString], bytes]

hashes:Dict[str,Any] = {
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

variable_size_hashes = { 'blake2b', 'blake2s', 'shake_128', 'shake_256' }
variable_constructor_hashes = { 'blake2b', 'blake2s' }
variable_digest_arg_hashes = { 'shake_128', 'shake_256' }

hash_docs_str = ', '.join(hashes)


def main() -> None:
  parser = ArgumentParser(description='Count lines of source code.')
  parser.add_argument('-hash', default='blake3', help=f'Hash algorithm to use: {hash_docs_str}.')
  parser.add_argument('-size', default=32, type=int, help='Digest size in bytes.')
  parser.add_argument('-lep128', action='store_true', help='Show lep128 result (default).')
  parser.add_argument('-lep62', action='store_true', help='Show lep62.')
  parser.add_argument('-b16', action='store_true', help='Show base16 result.')
  parser.add_argument('-b32', action='store_true', help='Show base32 result.')
  parser.add_argument('-b64', action='store_true', help='Show base64 result.')
  parser.add_argument('-url64', action='store_true', help='Show URL-safe base64 result.')

  parser.add_argument('paths', nargs='+', help='files to hash.')
  args = parser.parse_args()
  encoders:List[Tuple[str,_Encoder]] = []
  if args.lep128: encoders.append(('lep128', enc_lep128_to_utf8))
  if args.lep62:  encoders.append(('lep62', enc_lep62))
  if args.b16:    encoders.append(('b16', b16encode))
  if args.b32:    encoders.append(('b32', b32encode))
  if args.b64:    encoders.append(('b64', b64encode))
  if args.url64:  encoders.append(('url64', urlsafe_b64encode))
  if not encoders:
    encoders.append(('lep128', enc_lep128_to_utf8))

  try:
    hash_class = hashes[args.hash]
  except KeyError:
    errSL('error: invalid hash name:', args.hash)
    errSL('note: available hash functions:', *hashes)
    exit(1)

  hash_size = args.size
  if hash_size is None and args.hash in variable_digest_arg_hashes:
    exit(f'error: `-size` must be specified for hash function "{args.hash}".')

  size_arg = {'digest_size':args.size} if args.hash in variable_constructor_hashes else {}

  path_width = min(64, max(len(p) for p in args.paths))

  for path in args.paths:
    hasher = hash_class(**size_arg)
    hs = hash_size if args.hash in variable_digest_arg_hashes else None
    d = digest(hasher, path, hash_size=hs)
    msgs = []
    for label, encoder in encoders:
      msgs.append(f'{label}:{encoder(d).decode()}')
    print(f'{args.hash} {path:{path_width}}', *msgs)


def digest(hasher:Any, path:str, hash_size:Optional[int]) -> bytes:
  hash_chunk_size = 1 << 16
  #^ a quick timing experiment suggested that chunk sizes larger than this are not faster.
  try: f = open(path, 'rb')
  except IsADirectoryError: exit(f'expected a file but found a directory: {path}')
  while True:
    chunk = f.read(hash_chunk_size)
    if not chunk: break
    hasher.update(chunk)
  if hash_size: return hasher.digest(hash_size) # type: ignore[no-any-return]
  else: return hasher.digest() # type: ignore[no-any-return]


if __name__ == '__main__': main()
