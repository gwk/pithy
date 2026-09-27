# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pathlib import Path as FilePath
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pithy.fs import (_abs_start_and_top, abs_or_norm_path, abs_path, copy_to_dir, name_has_any_ext, path_rel_to_dir,
  PathHasNoDirError, walk_dirs_up)
from pithy.path import MixedAbsoluteAndRelativePathsError, Path, PathIsNotDescendantError
from utest import utest, utest_exc, utest_run, utest_seq


@utest_run
def test_copy_to_dir() -> None:
  for suffix in ('', '/', '//', '/.'):
    for path_type in (str, Path, FilePath):
      with TemporaryDirectory() as tmp:
        root = FilePath(tmp)
        src = root / 'src'
        dst = root / 'dst'
        src.mkdir()
        dst.mkdir()
        (src / 'new.txt').write_text('new')
        (dst / 'keep.txt').write_text('keep')
        copy_to_dir(path_type(str(src) + suffix), dst, follow=False)
        utest('keep', (dst / 'keep.txt').read_text)
        utest('new', (dst / 'src' / 'new.txt').read_text)
        utest(['keep.txt', 'src'], lambda: sorted(p.name for p in dst.iterdir()))

  with TemporaryDirectory() as tmp:
    root = FilePath(tmp)
    src = root / 'file.txt'
    dst = root / 'dst'
    src.write_text('file')
    copy_to_dir(Path(src), Path(dst), follow=False, create_dirs=True)
    utest('file', (dst / 'file.txt').read_text)


@utest_run
def test_copy_to_dir_requires_name() -> None:
  with patch('pithy.fs.make_dirs') as make_dirs, patch('pithy.fs.copy_path') as copy_path:
    for src in ('', '.', './', '/', '..', 'a/..'):
      utest_exc(ValueError, copy_to_dir, src, 'dst', follow=False, create_dirs=True)
    utest(0, lambda: make_dirs.call_count)
    utest(0, lambda: copy_path.call_count)


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
utest_exc(PathIsNotDescendantError('x', 'a'), walk_dirs_up, 'x/file.txt', 'a')


# _abs_start_and_top, the shared bounds check for find_file_up and find_project_dir.
# Absolute inputs make these tests independent of the working directory.

utest(('/a/b', '/'), _abs_start_and_top, '/a/b', '/') # The filesystem root is the default `top` for both callers.
utest(('/a/b', '/a'), _abs_start_and_top, '/a/b', '/a')
utest(('/a', '/a'), _abs_start_and_top, '/a', '/a')
utest(('/a/b', '/a'), _abs_start_and_top, '/a//b/', '/a/') # Both paths are normalized.

utest_exc(PathIsNotDescendantError('/b', '/a'), _abs_start_and_top, '/b', '/a')
utest_exc(PathIsNotDescendantError('/ab', '/a'), _abs_start_and_top, '/ab', '/a') # Compares components, not string prefixes.
