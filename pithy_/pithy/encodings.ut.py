# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from random import randbytes
from typing import Callable
from unicodedata import normalize

from pithy.encodings import (dec_b64url, dec_lep62, dec_lep128, dec_lep128_from_str, dec_lep128_from_utf8, enc_b64url,
  enc_lep62, enc_lep128, enc_lep128_to_str, lep_int_from_bytes)
from utest import utest, utest_exc


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

# The string decoders normalize to NFC, so NFD-decomposed input (e.g. from an HFS+ filename) still decodes.
accented = b'\xff\xff\xff'
utest('ÿÿÿF', enc_lep128_to_str, accented)
utest(accented, dec_lep128_from_str, normalize('NFD', enc_lep128_to_str(accented)))
utest(accented, dec_lep128_from_utf8, normalize('NFD', enc_lep128_to_str(accented)).encode('utf8'))
utest_exc(ValueError('ÿ\u0301'), dec_lep128_from_str, 'ÿ\u0301') # Combining mark that does not compose.


coders:list[tuple[Callable[[bytes],bytes], Callable[[bytes],bytes]]] = [
  (enc_b64url, dec_b64url),
  (enc_lep62, dec_lep62),
  (enc_lep128, dec_lep128),
]

for enc, dec in coders:
  for width in range(1, 65):
    for _ in range(16):
      b = randbytes(width)
      utest(b, dec, enc(b))
