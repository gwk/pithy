# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from random import randbytes
from typing import Any, Callable
from unicodedata import normalize

from pithy.encodings import (base128_alphabet, base128_alphabet_inverse, dec_b64url, dec_lep62, dec_lep128, dec_lep128_from_str,
  dec_lep128_from_utf8, enc_b64url, enc_lep62, enc_lep128, enc_lep128_to_str, enc_lep128_to_utf8, lep_decode, lep_encode,
  lep_int_from_bytes)
from utest import utest, utest_exc


utest(1, lep_int_from_bytes, b'')
utest(0x100, lep_int_from_bytes, b'\x00')
utest(0x101, lep_int_from_bytes, b'\x01')

utest(b'1', enc_lep62, b'')
utest(b'84', enc_lep62, b'\x00')
utest(b'94', enc_lep62, b'\x01')

utest(b'', dec_lep62, enc_lep62(b''))

# Decoding is strict: empty input, invalid characters, trailing zero digits and misaligned terminators are rejected.
utest_exc(ValueError('non-canonical encoding (empty or trailing zero digit): b\'\''), dec_lep62, b'')
utest_exc(ValueError('invalid character at index 1: b\'8-\''), dec_lep62, b'8-')
utest_exc(ValueError('non-canonical encoding (empty or trailing zero digit): b\'840\''), dec_lep62, b'840')
utest_exc(ValueError('terminator bit is not byte-aligned: b\'2\''), dec_lep62, b'2')


utest('1', enc_lep128_to_str, b'')
utest('02', enc_lep128_to_str, b'\x00')
utest('12', enc_lep128_to_str, b'\x01')

# The string decoders normalize to NFC, so NFD-decomposed input (e.g. from an HFS+ filename) still decodes.
accented = b'\xff\xff\xff'
utest('ÿÿÿF', enc_lep128_to_str, accented)
utest(accented, dec_lep128_from_str, normalize('NFD', enc_lep128_to_str(accented)))
utest(accented, dec_lep128_from_utf8, normalize('NFD', enc_lep128_to_str(accented)).encode('utf8'))
utest_exc(ValueError("invalid character: 'ÿ\u0301'"), dec_lep128_from_str, 'ÿ\u0301') # Combining mark that does not compose.

utest_exc(ValueError('non-canonical encoding (empty or trailing zero digit): b\'\''), dec_lep128, b'')
utest_exc(ValueError('invalid character at index 1: b\'0-\''), dec_lep128, b'0-')
utest_exc(ValueError('non-canonical encoding (empty or trailing zero digit): b\'020\''), dec_lep128, b'020')
utest_exc(ValueError('terminator bit is not byte-aligned: b\'2\''), dec_lep128, b'2')
utest_exc(ValueError('terminator bit is not byte-aligned: b\'00000001\''), dec_lep128, b'00000001') # Eight characters is never canonical.


def enc_lep128_generic(val:bytes) -> bytes: return lep_encode(val, base128_alphabet)
def dec_lep128_generic(val:bytes) -> bytes: return lep_decode(val, base128_alphabet, base128_alphabet_inverse)

coders:list[tuple[Callable[[bytes],Any], Callable[[Any],bytes]]] = [
  (enc_b64url, dec_b64url),
  (enc_lep62, dec_lep62),
  (enc_lep128, dec_lep128),
  (enc_lep128_generic, dec_lep128_generic),
  (enc_lep128_to_str, dec_lep128_from_str),
  (enc_lep128_to_utf8, dec_lep128_from_utf8),
]

for enc, dec in coders:
  for width in range(0, 65):
    for _ in range(16):
      b = randbytes(width)
      utest(b, dec, enc(b))

# The unrolled lep128 coder must match the generic scheme exactly.
for width in range(0, 65):
  b = randbytes(width)
  utest(enc_lep128_generic(b), enc_lep128, b)
