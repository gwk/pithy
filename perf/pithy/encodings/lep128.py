from random import randbytes
from timeit import repeat
from typing import Callable

from pithy.encodings import (b16decode, b16encode, b32decode, b32encode, b85decode, b85encode, dec_lep128, enc_lep128,
  standard_b64decode, standard_b64encode, urlsafe_b64decode, urlsafe_b64encode)


test_enc_fns = [enc_lep128, b85encode, standard_b64encode, urlsafe_b64encode, b32encode, b16encode]
test_dec_fns = [dec_lep128, b85decode, standard_b64decode, urlsafe_b64decode, b32decode, b16decode]
alg_names = ['lep128', 'b85', 'b64std', 'b64url', 'b32', 'b16']

def main() -> None:

  sizes = [1<<4, 1<<6, 1<<8, 1<<12, 1<<16]

  for size in sizes:
    reps = 1_000_000 // size
    print(f'\n\nsize: {size}; reps: {reps}')
    test_bytes = randbytes(size)

    bests = {}

    for alg_name, fn in zip(alg_names, test_enc_fns):
      name = fn.__name__
      times = repeat(stmt=lambda:fn(test_bytes), number=reps, repeat=5)
      times.sort()
      print(f'{name:20}: {times[0]:.06f}  {times[1]:.06f}  {times[2]:.06f}')

    for enc_fn, dec_fn in zip(test_enc_fns, test_dec_fns):
      name = dec_fn.__name__
      enc_bytes = enc_fn(test_bytes)
      times = repeat(stmt=lambda:dec_fn(enc_bytes), number=reps, repeat=5)
      times.sort()
      print(f'{name:20}: {times[0]:.06f}  {times[1]:.06f}  {times[2]:.06f}')


if __name__ == '__main__': main()
