# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.fs import (_abs_start_and_top, abs_or_norm_path, abs_path, name_has_any_ext, path_rel_to_dir, PathHasNoDirError,
  walk_dirs_up)
from pithy.path import MixedAbsoluteAndRelativePathsError, PathIsNotDescendentError
from utest import utest, utest_exc, utest_seq


# abs_or_norm_path normalizes inputs.
utest('.', abs_or_norm_path, './', False)
utest('/', abs_or_norm_path, '//', True)

# abs_path normalizes inputs.
utest('/', abs_path, '//')



utest(True, name_has_any_ext, 'a', frozenset())
utest(True, name_has_any_ext, '.a', frozenset())
utest(True, name_has_any_ext, 'a.e', frozenset(['.e']))
utest(True, name_has_any_ext, '.a.e', frozenset(['.e']))
utest(True, name_has_any_ext, 'a.f', frozenset(['.e', '.f']))
utest(True, name_has_any_ext, 'a.e.f', frozenset(['.f']))
utest(True, name_has_any_ext, 'a.e.f', frozenset(['.e.f']))

utest(False, name_has_any_ext, 'a', frozenset(['.e']))
utest(False, name_has_any_ext, 'a.b', frozenset(['.e']))
utest(False, name_has_any_ext, '.e', frozenset(['.e']))
utest(False, name_has_any_ext, 'a.e.f', frozenset(['.e']))

# path_rel_to_dir.
utest('.', path_rel_to_dir, '', '')
utest('a', path_rel_to_dir, 'a', '')
utest('a', path_rel_to_dir, 'a', '.')

utest('b', path_rel_to_dir, 'a/b', 'a/')

utest('b', path_rel_to_dir, '/a/b', '/a/')
utest('../b', path_rel_to_dir, '/a/b', '/a/c')


# walk_dirs_up: paths that don't exist on disk fall through to path_dir(), so these tests are filesystem-independent.

utest_seq(['a/b/c', 'a/b', 'a'], walk_dirs_up, 'a/b/c/file.txt', 'a')
utest_seq(['a/b/c', 'a/b'], walk_dirs_up, 'a/b/c/file.txt', 'a', include_top=False)

utest_seq(['a'], walk_dirs_up, 'a/file.txt', 'a')
# When dir_path == top and include_top=False, path_descendants still yields the shared path (include_end=True takes precedence).
utest_seq(['a'], walk_dirs_up, 'a/file.txt', 'a', include_top=False)

utest_exc(MixedAbsoluteAndRelativePathsError(('/a/b', 'a')), walk_dirs_up, '/a/b', 'a')
utest_exc(PathHasNoDirError('file.txt'), walk_dirs_up, 'file.txt', 'a')
utest_exc(PathIsNotDescendentError('x', 'a'), walk_dirs_up, 'x/file.txt', 'a')


# _abs_start_and_top, the shared bounds check for find_file_up and find_project_dir.
# Absolute inputs make these tests independent of the working directory.

utest(('/a/b', '/'), _abs_start_and_top, '/a/b', '/') # The filesystem root is the default `top` for both callers.
utest(('/a/b', '/a'), _abs_start_and_top, '/a/b', '/a')
utest(('/a', '/a'), _abs_start_and_top, '/a', '/a')
utest(('/a/b', '/a'), _abs_start_and_top, '/a//b/', '/a/') # Both paths are normalized.

utest_exc(PathIsNotDescendentError('/b', '/a'), _abs_start_and_top, '/b', '/a')
utest_exc(PathIsNotDescendentError('/ab', '/a'), _abs_start_and_top, '/ab', '/a') # Compares components, not string prefixes.
