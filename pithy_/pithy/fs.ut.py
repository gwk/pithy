# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import os as _os
from pathlib import PurePosixPath
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pithy.filestatus import file_permissions, is_link
from pithy.fs import (_abs_start_and_top, abs_or_norm_path, abs_path, copy_path, copy_to_dir, list_dir, make_dir, make_dirs,
  make_link, name_has_any_ext, path_rel_to_dir, PathHasNoDirError, walk_dirs_up)
from pithy.io import read_from_path, write_to_path
from pithy.path import MixedAbsoluteAndRelativePathsError, Path, PathIsNotDescendantError
from utest import utest, utest_exc, utest_run, utest_seq


@utest_run
def test_copy_to_dir() -> None:
  for suffix in ('', '/', '//', '/.'):
    for path_type in (str, Path, PurePosixPath): # PurePosixPath verifies that a foreign PathLike is accepted.
      with TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / 'src'
        dst = root / 'dst'
        make_dir(src)
        make_dir(dst)
        write_to_path(src / 'new.txt', 'new')
        write_to_path(dst / 'keep.txt', 'keep')
        copy_to_dir(path_type(str(src) + suffix), dst, follow=False)
        utest('keep', read_from_path, dst / 'keep.txt')
        utest('new', read_from_path, dst / 'src' / 'new.txt')
        utest(['keep.txt', 'src'], list_dir, dst)

  with TemporaryDirectory() as tmp:
    root = Path(tmp)
    src = root / 'file.txt'
    dst = root / 'dst'
    write_to_path(src, 'file')
    copy_to_dir(src, dst, follow=False, create_dirs=True)
    utest('file', read_from_path, dst / 'file.txt')


@utest_run
def test_copy_path() -> None:
  with TemporaryDirectory() as tmp:
    root = Path(tmp)
    src = root / 'src'
    make_dirs(src / 'sub')
    write_to_path(src / 'sub' / 'a.txt', 'a')
    write_to_path(src / '.hidden', 'h')
    make_link(src / 'sub' / 'a.txt', link=src / 'link') # Relative link: `sub/a.txt`.
    _os.chmod(src / 'sub' / 'a.txt', 0o600)
    # Symlinks are recreated when not following.
    dst = root / 'dst'
    copy_path(src, dst, follow=False)
    utest(['.hidden', 'link', 'sub'], list_dir, dst, hidden=True)
    utest(True, is_link, dst / 'link')
    utest('a', read_from_path, dst / 'link')
    umask = _os.umask(0)
    _os.umask(umask)
    utest(0o666 & ~umask, lambda: file_permissions(dst / 'sub' / 'a.txt', follow=True) & 0o777) # Data only; default mode applies.
    # Symlinks are dereferenced when following, and metadata is preserved on request.
    dst2 = root / 'dst2'
    copy_path(src, dst2, follow=True, preserve_meta=True)
    utest(False, is_link, dst2 / 'link')
    utest('a', read_from_path, dst2 / 'link')
    utest(0o600, lambda: file_permissions(dst2 / 'sub' / 'a.txt', follow=True) & 0o777)
    # Overwrite replaces an existing destination; without it an existing directory cannot be created.
    write_to_path(root / 'f', 'f')
    copy_path(root / 'f', dst / 'sub', follow=False, overwrite=True)
    utest('f', read_from_path, dst / 'sub')
    utest_exc(FileExistsError, copy_path, src / 'sub', dst2 / 'sub', follow=False, overwrite=False)
    # A destination inside the source is rejected before any change.
    utest_exc(ValueError, copy_path, src, src, follow=False)
    utest_exc(ValueError, copy_path, src, src / 'sub' / 'x', follow=False)


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
