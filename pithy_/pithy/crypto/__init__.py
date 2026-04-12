# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import urandom
from typing import Iterable

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import ECB


class AesSivCryptor:

  def __init__(self, key:bytes):
    self.aead = AESSIV(key)

  @classmethod
  def generate_key(cls) -> bytes:
    'Returns a 64 byte key.'
    return AESSIV.generate_key(512) # Corresponds to AES-256, since the key is split into encryption and MAC keys.


  def encrypt(self, *, data:bytes, assoc_data:bytes|Iterable[bytes]|None=None) -> bytes:
    'If assoc_data is not None, then the final element of assoc_data is used as the nonce.'
    ad:list[bytes]|None
    if assoc_data is None or isinstance(assoc_data, list): ad = assoc_data
    elif isinstance(assoc_data, bytes): ad = [assoc_data]
    else: ad = list(assoc_data)
    return self.aead.encrypt(data=data, associated_data=ad)


  def decrypt(self, data:bytes, assoc_data:bytes|Iterable[bytes]|None=None) -> bytes:
    'If assoc_data is not None, then the final element of assoc_data is used as the nonce.'
    ad:list[bytes]|None
    if assoc_data is None or isinstance(assoc_data, list): ad = assoc_data
    elif isinstance(assoc_data, bytes): ad = [assoc_data]
    else: ad = list(assoc_data)
    return self.aead.decrypt(data=data, associated_data=ad)



class OneWordCryptor:
  '''
  Encrypts a single 64-bit value using AES-128 in ECB mode.
  This creates a secure mapping between a 64 bit value and a 128-bit cyphertext.
  string.

  IMPORTANT: in many other contexts, the use of AES-128 in ECB mode is insecure.
  Please do not use this for anything other than encrypting single 64 bit values, e.g. integer keys.

  Derived from: https://andrew.carterlunn.co.uk/programming/2020/05/17/encrypting-integer-primary-keys.html.
  '''

  def __init__(self, key:bytes):
    'Initialize the cryptor with a 16 byte secret key.'
    if len(key) != 16: raise ValueError('The secret key for SingleWordCryptor must be 16 bytes long')
    algorithm = AES(key)
    self.cipher = Cipher(algorithm=algorithm, mode=ECB(), backend=default_backend())


  @staticmethod
  def generate_key() -> bytes:
    'Generate a suitable 16 byte secret key.'
    return urandom(16)


  def encrypt_int(self, val:int, signed:bool=False) -> bytes:
    'Encrypt a single 64 bit integer, either unsigned (default) or signed.'
    val_bytes = val.to_bytes(8, byteorder='little', signed=signed)
    encryptor = self.cipher.encryptor()
    return encryptor.update(val_bytes * 2) + encryptor.finalize()


  def decrypt_int(self, encrypted:bytes, signed:bool=False) -> int:
    'Decrypt a single 64 bit integer, either unsigned (default) or signed.'

    if len(encrypted) != 16: raise ValueError('The encrypted value must be 16 bytes long')

    decryptor = self.cipher.decryptor()
    decrypted = decryptor.update(encrypted) + decryptor.finalize()
    val0 = decrypted[:8]
    val1 = decrypted[8:]

    if val0 != val1: raise ValueError('The encrypted value is invalid')

    return int.from_bytes(val0, byteorder='little', signed=signed)
