#!/usr/bin/env python3

from os import urandom

from pithy.crypto import AesSivCryptor, OneWordCryptor
from utest import utest_val


k = AesSivCryptor.generate_key()
asc = AesSivCryptor(k)

for i in range(1, 32): # Empty data input is disallowed by the library.
  p = b'a' * i
  nonce = urandom(16)
  e = asc.encrypt(data=p, assoc_data=nonce)
  d = asc.decrypt(data=e, assoc_data=nonce)
  utest_val(p, d, p)



owc = OneWordCryptor(key=OneWordCryptor.generate_key())
for p in range(64):
  i = 1<<p
  e = owc.encrypt_int(i)
  d = owc.decrypt_int(e)
  utest_val(i, d, i)
