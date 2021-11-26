#!/usr/bin/env python3

from utest import utest
from pithy.encodings import enc_lep62, dec_lep62, enc_lep128, dec_lep128, enc_lep128_to_str
from pithy.encodings import lep_int_from_bytes
from random import randrange


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

coders = [
  (enc_lep62, dec_lep62),
  (enc_lep128, dec_lep128),
]

for enc, dec in coders:
  for width in range(1, 33):
    for _ in range(16):
      b = bytes(randrange(0x100) for _ in range(width))
      utest(b, dec, enc(b))

