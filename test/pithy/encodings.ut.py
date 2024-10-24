# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from random import randbytes
from typing import ByteString, Callable

from pithy.encodings import (dec_b64url, dec_lep62, dec_lep128, enc_b64url, enc_lep62, enc_lep128, enc_lep128_to_str,
  lep_int_from_bytes)
from utest import utest


utest(1, lep_int_from_bytes, b'')
utest(0x100, lep_int_from_bytes, b'\x00')
utest(0x101, lep_int_from_bytes, b'\x01')

utest(b'1', enc_lep62, b'')
utest(b'84', enc_lep62, b'\x00')
utest(b'94', enc_lep62, b'\x01')

utest(b'', dec_lep62, enc_lep62(b''))


utest('1', enc_lep128_to_str, b'')
utest('02', enc_lep128_to_str, b'\x00')
utest('12', enc_lep128_to_str, b'\x01')


coders:list[tuple[Callable[[ByteString],bytes], Callable[[bytes],bytes]]] = [
  (enc_b64url, dec_b64url),
  (enc_lep62, dec_lep62),
  (enc_lep128, dec_lep128),
]

for enc, dec in coders:
  for width in range(1, 65):
    for _ in range(16):
      b = randbytes(width)
      utest(b, dec, enc(b))
