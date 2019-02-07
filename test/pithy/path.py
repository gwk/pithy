#!/usr/bin/env python3

from utest import *
from pithy.path import *
from random import seed as rand_seed, choice as rand_choice

# abs_or_norm_path normalizes inputs.
utest('.', abs_or_norm_path, './', False)
utest('/', abs_or_norm_path, '//', True)

# abs_path normalizes inputs.
utest('/', abs_path, '//')

utest('a-s.ext', insert_path_stem_suffix, 'a.ext', '-s')


# is_norm_path.

utest(True, is_norm_path, '/')
utest(True, is_norm_path, '.')
utest(True, is_norm_path, '/')
utest(True, is_norm_path, '/...')
utest(True, is_norm_path, '.')
utest(True, is_norm_path, '..')
utest(True, is_norm_path, '...')

utest(False, is_norm_path, '//')
utest(False, is_norm_path, '/.')
utest(False, is_norm_path, '/..')
utest(False, is_norm_path, './')
utest(False, is_norm_path, './')

utest(True, is_path_abs, '/')
utest(False, is_path_abs, '.')

utest(True, is_sub_path, 'a/b')
utest(True, is_sub_path, 'a/.../b')
utest(True, is_sub_path, 'a/../b')
utest(True, is_sub_path, 'a/..')
utest(False, is_sub_path, 'a/../..')

# norm_path.

utest('.', norm_path, '')
utest('.', norm_path, '.')

utest('/', norm_path, '/')
utest('/', norm_path, '//')
utest('/', norm_path, '/..')
utest('/', norm_path, '/../../')
utest('/', norm_path, '/a/../../')
utest('/', norm_path, '/../a/../')

utest('/a', norm_path, '/a')
utest('/a', norm_path, '/a/')
utest('/a', norm_path, '//a//')

utest('a', norm_path, 'a')
utest('a', norm_path, './a')
utest('a', norm_path, 'a/.')


# Randomized test of norm_path against is_norm_path.
rand_seed(0)
for i in range(1<<10):
  path = ''.join(rand_choice('a/.') for i in range(8))
  if is_norm_path(path):
    utest(path, norm_path, path)
  else:
    n = norm_path(path)
    utest(True, is_norm_path, n)
