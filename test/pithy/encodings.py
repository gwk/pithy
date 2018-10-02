#!/usr/bin/env python3

from utest import *
from pithy.encodings import *
from pithy.encodings import _lep_int_from_bytes
from random import randrange


utest(1, _lep_int_from_bytes, b'')
utest(0x100, _lep_int_from_bytes, b'\x00')
utest(0x101, _lep_int_from_bytes, b'\x01')

utest(b'1', enc_lep62, b'')
utest(b'84', enc_lep62, b'\x00')
utest(b'94', enc_lep62, b'\x01')

utest(b'', dec_lep62, enc_lep62(b''))

for width in range(1, 65):
  for _ in range(16):
    b = bytes(randrange(0x100) for _ in range(width))
    utest(b, dec_lep62, enc_lep62(b))

utest('0', enc_b32, 0)
utest('-1', enc_b32, -1)
utest('1', enc_b32, 1)
utest('9', enc_b32, 9)
utest('A', enc_b32, 10)
utest('V', enc_b32, 31)
utest('10', enc_b32, 32)
