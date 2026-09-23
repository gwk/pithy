# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from base64 import (b16decode, b16encode, b32decode, b32encode, b85decode, b85encode, standard_b64decode, standard_b64encode,
  urlsafe_b64decode, urlsafe_b64encode)
from collections.abc import Buffer
from typing import Sequence, Sized
from unicodedata import normalize


_convenience_exports = (b16decode, b16encode, b32decode, b32encode, b85decode, b85encode)


def _byte_index(alphabet:bytes, char:int) -> int:
  try: return alphabet.index(char)
  except ValueError: return 0xff

# The base36LC alphabet consists of all ASCII numbers and lowercase letters.
base36LC_alphabet = b'0123456789abcdefghijklmnopqrstuvwxyz'
base36LC_alphabet_inverse = bytes(_byte_index(base36LC_alphabet, c) for c in range(0x100))
assert len(base36LC_alphabet) == 36

# The base58 alphabet as described by bitcoin removes 0, O, I, and l to improve readability.
base58_alphabet = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
base58_alphabet_inverse = bytes(_byte_index(base58_alphabet, c) for c in range(0x100))
assert len(base58_alphabet) == 58

# The base62 alphabet consists of all ASCII numbers and letters.
base62_alphabet = b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
base62_alphabet_inverse = bytes(_byte_index(base62_alphabet, c) for c in range(0x100))
assert len(base62_alphabet) == 62

# The base128 alphabet is a subset of the latin1 alphanumeric alphabet,
# chosen so that blocks of characters can be double-clicked to select the entire block.
# The only set that achieves this goal uses every letter character, as well as 0-9 and '_'.
# In VSCode, the double-click behavior also works for the numeric characters '²³¹¼½¾',
# but in macOS applications only the ten ASCII digits will double-click as a block.
# Older versions of macOS had problems outputting the 'ÿ' on the command line, but this appears to be fixed as of 2024-10.
# I believe this was a bug in editline/libedit.
# Unlike base58, this alphabet includes visually confusable characters.
# Storage cost: each character carries 7 bits, so the encoded length is 8/7 (1.14x) the input length in characters.
# As latin1 that is also the byte cost, better than base64's 4/3 (1.33x).
# As UTF-8, the 65 non-ASCII characters take two bytes each, so random input costs 8/7 * 193/128 = 1.72x its length in bytes.
# Caveats for using encoded values as filenames:
# * 56 of the characters have their case pair in the alphabet, so distinct values can collide on case-insensitive filesystems.
# * 53 of the characters decompose under NFD normalization;
# the string decoders apply NFC normalization before decoding to recover from this.
base128_alphabet = (
  '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyzª'
  'µºÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ').encode('latin1')

base128_alphabet_inverse = bytes(_byte_index(base128_alphabet, c) for c in range(0x100))
assert len(base128_alphabet) == 128


def lep_int_from_bytes(val:Sequence[int]) -> int:
  '''
  Create a (possibly very big) integer from the little endian interpretation of the bytes,
  and then add the equivalent of a final (most significant) 1 bit, which acts as a terminator when decoding.
  '''
  n = int.from_bytes(val, byteorder='little')
  bit_count = len(val)*8
  return n + (1<<bit_count)


def lep_encode(val:Sequence[int], alphabet:bytes) -> bytes:
  '''
  Encode a byte string using the specified base alphabet using the "little endian punctuated" scheme.
  This is quadratic in the input length for alphabets whose size is not a power of two.
  '''
  m = len(alphabet)
  res = bytearray()
  n = lep_int_from_bytes(val)
  while n:
    n, r = divmod(n, m)
    res.append(alphabet[r])
  return bytes(res)


def lep_decode(encoded:Sequence[int], alphabet:bytes, alphabet_inverse:bytes) -> bytes:
  '''
  Decode a byte string using the specified base alphabet and its inverse lookup table using the "little-endian punctuated"
  scheme.
  Decoding is strict: the input must be exactly what `lep_encode` produces.
  In particular a trailing `alphabet[0]` character is rejected, because the terminator bit makes the final digit nonzero.
  Like `lep_encode`, this is quadratic in the input length for alphabets whose size is not a power of two.
  '''
  m = len(alphabet)
  last_i = len(encoded) - 1
  if last_i < 0 or alphabet_inverse[encoded[last_i]] == 0:
    raise ValueError(f'non-canonical encoding (empty or trailing zero digit): {encoded!r}')
  n = 0
  for i in range(last_i, -1, -1): # Horner's rule, from the most significant digit down.
    a = alphabet_inverse[encoded[i]]
    if a >= m: raise ValueError(f'invalid character at index {i}: {encoded!r}')
    n = n*m + a
  bit_count = n.bit_length() - 1 # Position of the terminator bit.
  if bit_count % 8: raise ValueError(f'terminator bit is not byte-aligned: {encoded!r}')
  n ^= 1 << bit_count # Clear the terminator bit.
  return n.to_bytes(bit_count // 8, byteorder='little')


def enc_lep62(val:Sequence[int]) -> bytes:
  'Encode a byte string using the little endian punctuated base62 alphabet. This is quadratic in the input length.'
  return lep_encode(val, alphabet=base62_alphabet)

def dec_lep62(val:Sequence[int]) -> bytes:
  'Decode a byte string using the little endian punctuated base62 alphabet. This is quadratic in the input length.'
  return lep_decode(val, alphabet=base62_alphabet, alphabet_inverse=base62_alphabet_inverse)


def enc_lep128(val:Sequence[int]) -> bytes:
  'Encode a byte string using the little endian punctuated base128 alphabet.'
  a = base128_alphabet # Local alias for brevity.
  res = bytearray()
  i = -7
  chunk_end = (len(val) // 7) * 7
  for i in range(0, chunk_end, 7): # Step over 7 bytes at a time.
    n = int.from_bytes(val[i:i+7], byteorder='little')
    res.append(a[n & 0x7f]) # Low 7 bits of n.
    res.append(a[(n >> 7) & 0x7f])
    res.append(a[(n >> 14) & 0x7f])
    res.append(a[(n >> 21) & 0x7f])
    res.append(a[(n >> 28) & 0x7f])
    res.append(a[(n >> 35) & 0x7f])
    res.append(a[(n >> 42) & 0x7f])
    res.append(a[(n >> 49)])
  tail = val[i+7:] # Get the remaining bytes.
  assert len(tail) < 7
  n = int.from_bytes(tail, byteorder='little') + (1<<(len(tail)*8)) # Append the terminating bit.
  while n:
    n, r = divmod(n, 128)
    res.append(a[r])
  return bytes(res)


def dec_lep128(encoded:Sequence[int]) -> bytes:
  '''
  Decode a byte string using the little endian punctuated base128 alphabet.
  Decoding is strict: the input must be exactly what `enc_lep128` produces.
  In particular a trailing `base128_alphabet[0]` character is rejected, because the terminator bit makes the final digit nonzero.
  '''
  res = bytearray()
  n = 0
  v = 0
  last_i = len(encoded) - 1
  for i, c in enumerate(encoded):
    j = i % 8
    v = base128_alphabet_inverse[c]
    if v >= 128: raise ValueError(f'invalid character at index {i}: {encoded!r}')
    n += v << (7*j)
    if j == 7 and i < last_i:
      res.extend(n.to_bytes(7, byteorder='little'))
      n = 0
  if v == 0: raise ValueError(f'non-canonical encoding (empty or trailing zero digit): {encoded!r}')
  # Handle the final chunk specially, since it has the terminating bit.
  while n > 1:
    n, r = divmod(n, 0x100)
    res.append(r)
  if n != 1: raise ValueError(f'terminator bit is not byte-aligned: {encoded!r}')
  return bytes(res)


def enc_lep128_to_str(val:Sequence[int]) -> str:
  'Encode a byte string using the little endian punctuated base128 alphabet, returning a string.'
  return enc_lep128(val).decode('latin1')


def dec_lep128_from_str(val:str) -> bytes:
  '''
  Decode a string using the little endian punctuated base128 alphabet.
  The string is first normalized to NFC, because every character of the alphabet is NFC-stable,
  but many of them decompose under NFD (e.g. when passed through an HFS+ filename).
  '''
  try: return dec_lep128(normalize('NFC', val).encode('latin1'))
  except UnicodeEncodeError as e: raise ValueError(f'invalid character: {val!r}') from e


def enc_lep128_to_utf8(val:Sequence[int]) -> bytes:
  'Encode a byte string using the little endian punctuated base128 alphabet, returning a UTF-8 byte string.'
  return enc_lep128(val).decode('latin1').encode('utf8')


def dec_lep128_from_utf8(val:Sequence[int]) -> bytes:
  'Decode a UTF-8 byte string using the little endian punctuated base128 alphabet.'
  if not isinstance(val, (bytes, bytearray)): val = bytes(val) # memoryview does not have the decode() method.
  return dec_lep128_from_str(val.decode('utf8'))


def enc_b64url(val:str|Buffer, pad:bool=False) -> bytes:
  '''
  Encode a byte string using the base64url alphabet (ending in "-_").
  If `pad` is False (the default), then trailing "=" characters are removed from the result.
  See: https://datatracker.ietf.org/doc/html/rfc4648#section-5.
  '''
  if isinstance(val, str): val = val.encode()
  b = urlsafe_b64encode(val)
  if not pad: b = b.rstrip(b'=')
  return b


def dec_b64url(val:str|Buffer) -> bytes:
  '''
  Decode a byte string using the base64url alphabet (ending in "-_").
  If the input is not a multiple of 4 bytes, then "=" characters are added to the end prior to passing to `urlsafe_b64decode`.
  '''
  if isinstance(val, str): val = val.encode()

  if isinstance(val, Sized):
    length = len(val)
  else:
    mv = memoryview(val)
    assert mv.ndim == 1 and mv.itemsize == 1
    length = mv.nbytes
  mod4 = length % 4
  if mod4:
    val = bytes(val) + b'=' * (4 - mod4)
  return urlsafe_b64decode(val)


def enc_b64std_str(val:str|Buffer) -> str:
  'Encode a string or bytes as base64 using the standard alphabet (ending in "+/"), returning a string.'
  if isinstance(val, str): val = val.encode()
  return standard_b64encode(val).decode()


def dec_b64std_str(val:str|Buffer) -> str:
  'Decode a base64 string or bytes in the standard alphabet, returning another string.'
  return standard_b64decode(val).decode()
