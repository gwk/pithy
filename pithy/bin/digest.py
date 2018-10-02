# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'print file hashes. first argument is the format; remaining args are the paths.'

from ..encodings import enc_lep62
from ..io import errSL
from argparse import ArgumentParser
from base64 import b16encode, b32encode, b64encode, urlsafe_b64encode
from typing import Any, ByteString, Callable, List, TypeVar, Tuple, Union
import hashlib


_ByteString = TypeVar('_ByteString', ByteString, bytes, bytearray, memoryview) # Hack around the typeshed defs from base64.
_Encoder = Callable[[_ByteString], bytes]

hashes = {
  'sha1'   : hashlib.sha1,
  'sha224' : hashlib.sha224,
  'sha256' : hashlib.sha256,
  'sha384' : hashlib.sha384,
  'sha512' : hashlib.sha512,
  'md5' : hashlib.md5,
}

hash_docs_str = ', '.join(hashes)


def main() -> None:
  parser = ArgumentParser(description='Count lines of source code.')
  parser.add_argument('-hash', default='sha256', help=f'Hash algorithm to use: {hash_docs_str}.')
  parser.add_argument('-lep62', action='store_true', help='Show lep62 result (default).')
  parser.add_argument('-b16', action='store_true', help='Show base16 result.')
  parser.add_argument('-b32', action='store_true', help='Show base32 result.')
  parser.add_argument('-b64', action='store_true', help='Show base64 result.')
  parser.add_argument('-url64', action='store_true', help='Show URL-safe base64 result.')

  parser.add_argument('paths', nargs='+', help='files to hash.')
  args = parser.parse_args()
  encoders:List[Tuple[str,_Encoder]] = []
  if args.lep62:  encoders.append(('lep62', enc_lep62))
  if args.b16:    encoders.append(('b16', b16encode))
  if args.b32:    encoders.append(('b32', b32encode))
  if args.b64:    encoders.append(('b64', b64encode))
  if args.url64:  encoders.append(('url64', urlsafe_b64encode))
  if not encoders:
    encoders.append(('lep62', enc_lep62))

  try:
    hash_class = hashes[args.hash]
  except KeyError:
    errSL('invalid hash name:', args.hash)
    errSL('available hash functions:', *hashes)
    exit(1)

  path_width = min(64, max(len(p) for p in args.paths))

  for path in args.paths:
    d = digest(hash_class, path)
    msgs = []
    for label, encoder in encoders:
      msgs.append(f'{label}:{encoder(d).decode()}')
    print(f'{args.hash} {path:{path_width}}', *msgs)


def digest(hash_class: Callable[[],Any], path:str) -> bytes:
  hash_chunk_size = 1 << 16
  #^ a quick timing experiment suggested that chunk sizes larger than this are not faster.
  try: f = open(path, 'rb')
  except IsADirectoryError: exit(f'expected a file but found a directory: {path}')
  h = hash_class()
  while True:
    chunk = f.read(hash_chunk_size)
    if not chunk: break
    h.update(chunk)
  return h.digest() # type: ignore


if __name__ == '__main__': main()
