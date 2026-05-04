# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.fs import name_has_any_ext, PathHasNoDirError, walk_dirs_up
from pithy.path import MixedAbsoluteAndRelativePathsError, PathIsNotDescendantError
from utest import utest, utest_exc, utest_seq


# walk_dirs_up: paths that don't exist on disk fall through to path_dir(), so these tests are filesystem-independent.

utest_seq(['a/b/c', 'a/b', 'a'], walk_dirs_up, 'a/b/c/file.txt', 'a')
utest_seq(['a/b/c', 'a/b'], walk_dirs_up, 'a/b/c/file.txt', 'a', include_top=False)

utest_seq(['a'], walk_dirs_up, 'a/file.txt', 'a')
# When dir_path == top and include_top=False, path_descendants still yields the shared path (include_end=True takes precedence).
utest_seq(['a'], walk_dirs_up, 'a/file.txt', 'a', include_top=False)

utest_exc(MixedAbsoluteAndRelativePathsError(('/a/b', 'a')), walk_dirs_up, '/a/b', 'a')
utest_exc(PathHasNoDirError('file.txt'), walk_dirs_up, 'file.txt', 'a')
utest_exc(PathIsNotDescendantError('x', 'a'), walk_dirs_up, 'x/file.txt', 'a')


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
