# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from secrets import randbelow

base36LC_chars = '0123456789abcdefghijklmnopqrstuvwxyz'


def gen_password(length:int=24, dash_every:int=6) -> str:
  n = len(base36LC_chars)
  chars = []
  for i in range(length):
    if i and i%dash_every == 0:
      chars.append('-')
    chars.append(base36LC_chars[randbelow(n)])
  return ''.join(chars)
