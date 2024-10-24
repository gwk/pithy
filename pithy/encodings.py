# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from base64 import standard_b64decode, standard_b64encode, urlsafe_b64decode, urlsafe_b64encode
from typing import ByteString


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
base128_alphabet = (
  '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyzª'
  'µºÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ').encode('latin1')

base128_alphabet_inverse = bytes(_byte_index(base128_alphabet, c) for c in range(0x100))
assert len(base128_alphabet) == 128


def lep_int_from_bytes(val:ByteString) -> int:
  '''
  Create a (possibly very big) integer from the little endian interpretation of the bytes,
  and then add the equivalent of a final 1 bit, which acts as a terminator when decoding.
  '''
  n = int.from_bytes(val, byteorder='little')
  return n + (1<<(len(val)*8))


def lep_encode(val:ByteString, alphabet:bytes) -> bytes:
  'Encode a byte string using the specified base alphabet using the "little endian punctuated" scheme.'
  m = len(alphabet)
  res = bytearray()
  n = lep_int_from_bytes(val)
  while n:
    n, r = divmod(n, m)
    res.append(alphabet[r])
  return bytes(res)


def lep_decode(encoded:ByteString, alphabet:bytes, alphabet_inverse:bytes) -> bytes:
  'Decode a byte string using the specified base alphabet and its inverse lookup table using the "little-endian punctuated" scheme.'
  m = len(alphabet)
  n = 0
  for i, char in enumerate(encoded):
    a = alphabet_inverse[char]
    if a >= m: raise ValueError(encoded)
    n += (m**i) * a
  res = bytearray()
  while n > 1:
    n, r = divmod(n, 0x100)
    res.append(r)
  if n != 1: raise ValueError(encoded)
  return bytes(res)


def enc_lep62(val:ByteString) -> bytes:
  'Encode a byte string using the little endian punctuated base62 alphabet.'
  return lep_encode(val, alphabet=base62_alphabet)

def dec_lep62(val:ByteString) -> bytes:
  'Decode a byte string using the little endian punctuated base62 alphabet.'
  return lep_decode(val, alphabet=base62_alphabet, alphabet_inverse=base62_alphabet_inverse)


def enc_lep128(val:ByteString) -> bytes:
  'Encode a byte string using the little endian punctuated base128 alphabet.'
  a = base128_alphabet # Local alias for brevity.
  res = bytearray()
  i = -7
  for i in range(0, len(val)//7, 7): # Step over 7 bytes at a time.
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
  n = int.from_bytes(tail, byteorder='little') + (1<<(len(tail)*8)) # Append the terminating bit.
  while n:
    n, r = divmod(n, 128)
    res.append(a[r])
  return bytes(res)


def dec_lep128(encoded:ByteString) -> bytes:
  'Decode a byte string using the little endian punctuated base128 alphabet.'
  res = bytearray()
  i = -1
  n = 0
  last_i = len(encoded) - 1
  for i, c in enumerate(encoded):
    j = i % 8
    c = encoded[i]
    v = base128_alphabet_inverse[c]
    if v >= 128: raise ValueError(encoded)
    n += v << (7*j)
    if j == 7 and i < last_i:
      res.extend(n.to_bytes(7, byteorder='little'))
      n = 0
  # Handle the final chunk specially, since it is has the terminating bit.
  j = i % 8
  while n > 1:
    n, r = divmod(n, 0x100)
    res.append(r)
  if n != 1: raise ValueError(encoded)
  return bytes(res)


def enc_lep128_to_str(val:ByteString) -> str:
  'Encode a byte string using the little endian punctuated base128 alphabet, returning a string.'
  return enc_lep128(val).decode('latin1')


def dec_lep128_from_str(val:str) -> bytes:
  'Decode a string using the little endian punctuated base128 alphabet.'
  return dec_lep128(val.encode('latin1'))


def enc_lep128_to_utf8(val:ByteString) -> bytes:
  'Encode a byte string using the little endian punctuated base128 alphabet, returning a UTF-8 byte string.'
  return enc_lep128(val).decode('latin1').encode('utf8')


def dec_lep128_from_utf8(val:ByteString) -> bytes:
  'Decode a UTF-8 byte string using the little endian punctuated base128 alphabet.'
  if not isinstance(val, (bytes, bytearray)): val = bytes(val) # memoryview does not have the decode() method.
  return dec_lep128(val.decode('utf8').encode('latin1'))


def enc_b64url(val:ByteString, pad=False) -> bytes:
  '''
  Encode a byte string using the base64url alphabet (ending in "-_").
  If `pad` is False (the default), then trailing "=" characters are removed from the result.
  '''
  b = urlsafe_b64encode(val)
  if not pad: b = b.rstrip(b'=')
  return b


def dec_b64url(val:ByteString) -> bytes:
  '''
  Decode a byte string using the base64url alphabet (ending in "-_").
  If the input is not a multiple of 4 bytes, then "=" characters are added to the end prior to passing to `urlsafe_b64decode`.
  '''
  mod4 = len(val) % 4
  if mod4:
    val = bytes(val) + b'=' * (4 - mod4)
  return urlsafe_b64decode(val)


def enc_b64std_str(s:str|ByteString) -> str:
  'Encode a string as base64 using the standard alphabet, returning a string.'
  if isinstance(s, str): s = s.encode()
  return standard_b64encode(s).decode()


def dec_b64std_str(s:str) -> str:
  'Decode a base64 string, returning another string.'
  return standard_b64decode(s).decode()
