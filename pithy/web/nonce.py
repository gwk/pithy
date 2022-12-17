# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from secrets import token_urlsafe
from time import time


class NonceStorage:
  '''
  Store nonces in memory with associated expiry times.
  '''

  def __init__(self, num_rand_bytes:int, expiry_duration:int):
    self.storage:dict[str,float] = {}
    self.num_rand_bytes = num_rand_bytes
    self.expiry_duration = expiry_duration
    self.purge_threshold_len = 1


  def __len__(self) -> int: return len(self.storage)


  def generate(self) -> str:
    if self.needs_purge(): self.purge()
    nonce = token_urlsafe(self.num_rand_bytes)
    if nonce in self.storage: # Unlikely, unless num_rand_bytes is too low. Try one more time.
      nonce = token_urlsafe(self.num_rand_bytes)
      if nonce in self.storage: raise Exception('nonce collision')
    self.storage[nonce] = time() + self.expiry_duration
    return nonce


  def validate(self, nonce:str) -> bool:
    try: exp_t = self.storage.pop(nonce)
    except KeyError: return False
    return exp_t > time()


  def needs_purge(self) -> bool:
    return len(self.storage) > self.purge_threshold_len


  def purge(self) -> None:
    curr_t = time()
    self.storage = { n : exp_t for (n, exp_t) in self.storage.items() if exp_t > curr_t }
    new_len = len(self.storage)
    new_threshold = new_len * 3 // 2 + 1
    self.purge_threshold_len = new_threshold
