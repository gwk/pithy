# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, List, ByteString, Union


def _byte_index(alphabet:bytes, char:int) -> int:
  try: return alphabet.index(char)
  except ValueError: return 0xff

base62_alphabet = b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
base62_alphabet_inverse = bytes(_byte_index(base62_alphabet, c) for c in range(0x100))
assert len(base62_alphabet) == 62

base58_alphabet = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
base58_alphabet_inverse = bytes(_byte_index(base58_alphabet, c) for c in range(0x100))
assert len(base58_alphabet) == 58


def _lep_int_from_bytes(val:ByteString) -> int:
  '''
  Create a (big) integer from the little-endian interpretation of the bytes,
  and then add a leading 1, which will act as a terminator when decoding.
  '''
  n = int.from_bytes(val, byteorder='little')
  return n + (1<<(len(val)*8))


def lep_encode(val:ByteString, alphabet:bytes) -> bytes:
  m = len(alphabet)
  res = bytearray()
  n = _lep_int_from_bytes(val)
  while n:
    n, r = divmod(n, m)
    res.append(alphabet[r])
  return bytes(res)

def lep_decode(val:ByteString, alphabet:bytes, alphabet_inverse:bytes) -> bytes:
  m = len(alphabet)
  n = 0
  for i, char in enumerate(val):
    a = alphabet_inverse[char]
    if a >= m: raise ValueError(val)
    n += (m**i) * a
  res = bytearray()
  while n > 1:
    n, r = divmod(n, 0x100)
    res.append(r)
  if n != 1: raise ValueError(val)
  return bytes(res)


def enc_lep62(val:ByteString) -> bytes:
  return lep_encode(val, alphabet=base62_alphabet)

def dec_lep62(val:ByteString) -> bytes:
  return lep_decode(val, alphabet=base62_alphabet, alphabet_inverse=base62_alphabet_inverse)


def enc_b32(val:int) -> str:
  if not isinstance(val, int): raise TypeError
  chars = []
  if val == 0: return '0'
  neg = (val < 0)
  if neg: val = -val
  while val > 0:
    digit = val & 0x1f # low five bits.
    val >>= 5
    chars.append(chr((0x30 if digit < 10 else 0x37) + digit))
  if neg: chars.append('-')
  return ''.join(reversed(chars))
