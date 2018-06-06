#!/usr/bin/env python3

import re
from itertools import chain
from sys import argv
from time import time
from typing import *

from pithy.ansi import *
from pithy.diff import *
from pithy.fs import *
from pithy.io import *
from pithy.task import * # type: ignore


_T = TypeVar('_T')

build_dir = '_build/test-diff'

def main() -> None:
  args = argv[1:]
  d = 0
  t0 = 0
  t1 = 0
  pairs = args or [line.strip() for pairs_path in list_dir_paths(f'{build_dir}/pairs') for line in open(pairs_path)]
  for pair_str in err_progress(pairs):
    obj_a, obj_b = pair_str.split('_')
    not_same, d0, d1 = test_pair(obj_a, obj_b)
    d += not_same
    t0 += d0
    t1 += d1
  outL(f'not same: {d}; time: {t0:0.3f} -> {t1:0.3f}')


def test_pair(obj_a:str, obj_b:str) -> Tuple[int, float, float]:
  seq_a = list(open(f'{build_dir}/objects/{obj_a[:2]}/{obj_a}'))
  seq_b = list(open(f'{build_dir}/objects/{obj_b[:2]}/{obj_b}'))

  a0 = 'difflib'
  a1 = 'patience'

  t0_start = time()
  d0 = calc_diff(seq_a, seq_b, algorithm=a0)
  t0 = time() - t0_start
  validate_diff(seq_a, seq_b, d0)

  t1_start = time()
  d1 = calc_diff(seq_a, seq_b, algorithm=a1)
  t1 = time() - t1_start
  validate_diff(seq_a, seq_b, d1)

  not_same = (d0 != d1)
  if not_same:
    outL(f'\n{obj_a}_{obj_b}:')
    outL(f'{a0}:')
    d0, d1 = trim_common_ends(d0, d1)
    dump_diff(seq_a, seq_b, d0)
    outL('----')
    outL(f'{a1}:')
    dump_diff(seq_a, seq_b, d1)
    outL('---')
  return not_same, t0, t1


def dump_diff(seq_a:List[_T], seq_b:List[_T], diff:Diff) -> None:
  for a, b in diff:
    if a and b:
      i = 0
      for i in a[:3]: outZ(f'{TXT_D}{i+1:03}| ', seq_a[i], RST)
      j = max(i+1, a.stop-3)
      if i+1 < j: outL()
      for j in range(j, a.stop): outZ(f'{TXT_D}{j+1:03}| ', seq_a[j], RST)
    elif a:
      for i in a: outZ(f'{TXT_D}{i+1:03}{TXT_R}- ', seq_a[i], RST)
    elif b:
      for i in b: outZ(f'{TXT_D}{i+1:03}{TXT_G}+ ', seq_b[i], RST)


if __name__ == '__main__': main()
