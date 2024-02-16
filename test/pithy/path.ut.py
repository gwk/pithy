# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from random import choice as rand_choice, seed as rand_seed

from pithy.path import (abs_or_norm_path, abs_path, insert_path_stem_suffix, is_norm_path, is_path_abs, is_sub_path, norm_path,
  path_descendants, path_rel_to_dir, PathIsNotDescendantError, split_stem_ext, split_stem_multi_ext)
from utest import utest, utest_exc


# abs_or_norm_path normalizes inputs.
utest('.', abs_or_norm_path, './', False)
utest('/', abs_or_norm_path, '//', True)

# abs_path normalizes inputs.
utest('/', abs_path, '//')

utest('a-s.ext', insert_path_stem_suffix, 'a.ext', '-s')

# split_stem_ext.
utest(('', ''), split_stem_ext, '')
utest(('a', ''), split_stem_ext, 'a')
utest(('a', '.'), split_stem_ext, 'a.')
utest(('a', '.ext'), split_stem_ext, 'a.ext')
utest(('a.b', '.ext'), split_stem_ext, 'a.b.ext')
utest(('d/a.b', '.ext'), split_stem_ext, 'd/a.b.ext')
utest(('d/.a', ''), split_stem_ext, 'd/.a')
utest(('d/.a', '.ext'), split_stem_ext, 'd/.a.ext')

# split_stem_multi_ext.
utest(('', ''), split_stem_multi_ext, '')
utest(('a', ''), split_stem_multi_ext, 'a')
utest(('a', '.'), split_stem_multi_ext, 'a.')
utest(('a', '.ext'), split_stem_multi_ext, 'a.ext')
utest(('a', '.b.ext'), split_stem_multi_ext, 'a.b.ext')
utest(('d/a', '.b.ext'), split_stem_multi_ext, 'd/a.b.ext')
utest(('d/.a', ''), split_stem_multi_ext, 'd/.a')
utest(('d/.a', '.ext'), split_stem_multi_ext, 'd/.a.ext')


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


# path_descendants.
utest_exc(PathIsNotDescendantError, path_descendants, 'a', 'b')

utest(('a',), path_descendants, 'a', 'a')
utest(('a',), path_descendants, 'a', 'a', include_start=False)
utest(('a',), path_descendants, 'a', 'a', include_end=False)
utest((), path_descendants, 'a', 'a', include_start=False, include_end=False)

utest(('a', 'a/b', 'a/b/c'), path_descendants, 'a/', 'a/b/c')
utest(('a/b', 'a/b/c'), path_descendants, 'a/', 'a/b/c', include_start=False)
utest(('a', 'a/b'), path_descendants, 'a/', 'a/b/c', include_end=False)
utest(('a/b',), path_descendants, 'a/', 'a/b/c', include_start=False, include_end=False)

# path_rel_to_dir.
utest('.', path_rel_to_dir, '', '')
utest('a', path_rel_to_dir, 'a', '')
utest('a', path_rel_to_dir, 'a', '.')

utest('b', path_rel_to_dir, 'a/b', 'a/')

utest('b', path_rel_to_dir, '/a/b', '/a/')
utest('../b', path_rel_to_dir, '/a/b', '/a/c')
