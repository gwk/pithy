# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import pickle
from copy import copy, deepcopy
from operator import ge, gt, le, lt, truediv
from os import fspath
from pathlib import PurePosixPath
from random import choice as rand_choice, seed as rand_seed

from pithy.path import (AbsolutePathError, insert_path_stem_suffix, InteriorDotDotError, is_norm_path, is_path_abs, is_sub_path,
  MixedAbsoluteAndRelativePathsError, norm_path, Path, path_descendants, PathIsNotDescendantError, split_stem_ext,
  split_stem_multi_ext)
from utest import utest, utest_exc, utest_run


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
utest(True, is_norm_path, '/...')
utest(True, is_norm_path, '.')
utest(True, is_norm_path, '..')
utest(True, is_norm_path, '...')
utest(True, is_norm_path, 'a')
utest(True, is_norm_path, 'a/b')
utest(True, is_norm_path, '../a')
utest(True, is_norm_path, '.h')
utest(True, is_norm_path, 'a/.h')
utest(True, is_norm_path, '.h/b')
utest(True, is_norm_path, '.h/.h')
utest(True, is_norm_path, '../.h')

utest(False, is_norm_path, '//')
utest(False, is_norm_path, '/.')
utest(False, is_norm_path, '/..')
utest(False, is_norm_path, './')
utest(False, is_norm_path, 'a//b')
utest(False, is_norm_path, 'a/./b')

utest(True, is_path_abs, '/')
utest(False, is_path_abs, '.')

utest(True, is_sub_path, 'a/b')
utest(True, is_sub_path, 'a/.../b')
utest(True, is_sub_path, 'a/../b')
utest(True, is_sub_path, 'a/..')
utest(False, is_sub_path, 'a/../..')
utest(True, is_sub_path, 'a')
utest(True, is_sub_path, '.')
utest(False, is_sub_path, '..')
utest(False, is_sub_path, '/a')
utest(False, is_sub_path, '/a/b')
utest(False, is_sub_path, '../a')

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
utest('a', norm_path, 'a/b/..')
utest('a/b/c', norm_path, 'a/b/c')
utest('../a', norm_path, '../a')
utest('../../a', norm_path, '../../a')
utest('..', norm_path, '../a/..')


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


@utest_run
def test_path() -> None:
  class PathInput:
    def __init__(self, value:str) -> None:
      self.value = value
      self.calls = 0

    def __fspath__(self) -> str:
      self.calls += 1
      return self.value

  class BytesInput:
    def __fspath__(self) -> bytes: return b'a'

  input_path = PathInput('a//b/')
  from_input = Path(input_path)
  utest(Path('a/b'), lambda: from_input)
  utest(1, lambda: input_path.calls)
  input_path.value = 'changed'
  utest(Path('a/b'), lambda: from_input)
  utest(Path('a/b'), Path, PurePosixPath('a/b'))
  utest(Path('a/b'), Path, Path('a/b/'))
  utest('a/b', fspath, Path('a/b/'))
  utest('/', fspath, Path('/'))
  utest(PurePosixPath('/a/b'), PurePosixPath, Path('/a/b/'))

  path = Path('a//b/./c/')
  utest(('a', 'b', 'c'), lambda: path.parts)
  utest(False, lambda: path.is_abs)
  utest('a/b/c', str, path)
  utest("Path('a/b/c')", repr, path)
  utest(Path('.'), Path)
  utest_exc(ValueError, Path, '')
  utest_exc(ValueError, Path, PathInput(''))
  utest('.', str, Path('.'))
  utest('.', str, Path('./'))
  utest("Path('.')", repr, Path('./'))
  utest('..', str, Path('../'))
  utest('a/..', str, Path('a/../'))
  utest(Path('a/..'), Path, 'a/./..')
  utest('.', str, Path('./.'))
  utest('/', str, Path('//'))
  utest(Path('/'), Path, '/.')
  utest(Path('x'), Path, 'x/.')
  utest('x', str, Path('x/./.'))
  utest('x', str, Path('x/./'))
  utest('x/..', str, Path('x/../.'))
  for spelling, with_slash in (('.', './'), ('..', '../'), ('/', '/'), ('a', 'a/'), ('/a/b/', '/a/b/'), ('a/..', 'a/../')):
    utest(with_slash, Path(spelling).str_with_slash)
  utest('a\\b', str, Path('a\\b'))
  utest('~/a\n\udcff', str, Path('~/a\n\udcff'))
  raw_name = b'a/\xff'
  utest(raw_name, lambda: str(Path(raw_name.decode('utf-8', 'surrogateescape'))).encode('utf-8', 'surrogateescape'))
  utest_exc(ValueError, Path, 'a\0b')
  utest_exc(TypeError, Path, b'a')
  utest_exc(TypeError, Path, BytesInput())
  for attr, value in (('parts', ()), ('is_abs', True)):
    utest_exc(AttributeError, setattr, path, attr, value)
    utest_exc(AttributeError, delattr, path, attr)
  for p in (path, path.parent):
    lookup = {p: 'value'}
    utest_exc(AttributeError, Path.__init__, p, 'changed')
    utest('value', lookup.__getitem__, Path(str(p)))
  utest_exc(TypeError, type, 'ChildPath', (Path,), {})
  for p in (Path('.'), Path('/'), Path('a/b'), Path('../a'), Path('\udcff')):
    utest(p, lambda: p.__reduce__()[0](*p.__reduce__()[1]))
    for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
      utest(p, pickle.loads, pickle.dumps(p, protocol))
    utest(True, lambda: copy(p) is p)
    utest(True, lambda: deepcopy(p) is p)
  utest((Path('a'), Path('a')), deepcopy, (Path('a'), Path('a')))
  utest(True, bool, Path('.'))

  utest(Path('a/b'), lambda: Path('a/') / 'b/')
  utest(Path('a/b'), lambda: Path('a') / 'b')
  utest(Path('a'), lambda: Path('.') / 'a')
  utest(Path('a'), lambda: Path('a') / './')
  utest(Path('a'), lambda: Path('a') / '.') # Joining `.` is the identity.
  utest(Path('a'), lambda: Path('a') / Path('.'))
  utest(Path('a/..'), lambda: Path('a') / '..')
  utest(Path('a/b'), lambda: Path('a') / 'b/.')
  for base in (Path('.'), Path('/'), Path('a'), Path('../a')):
    for dot in ('.', './', Path('.'), PurePosixPath('.'), PurePosixPath('')):
      utest(base, truediv, base, dot)
      utest(base, base.join, [dot])
    utest(base, base.join, ['./', Path('.')])
  joined_input = PathInput('b/')
  joined = Path('a') / joined_input
  utest(Path('a/b'), lambda: joined)
  utest(1, lambda: joined_input.calls)
  joined_input.value = 'changed'
  utest(Path('a/b'), lambda: joined)
  utest(Path('a/b'), lambda: Path('a') / PurePosixPath('b'))
  utest_exc(AbsolutePathError, lambda: Path('a') / '/b')
  utest_exc(TypeError, truediv, Path('a'), 1)
  utest_exc(TypeError, truediv, Path('a'), BytesInput())

  utest(Path('/a/b/c/d/e'), Path('/a').join, ['b', PurePosixPath('c')], Path('d'), 'e/')
  utest(Path('a/b/c'), Path('a').join, (part for part in ('b', 'c')))
  utest(Path('a/long-name'), Path('a').join, 'long-name')
  utest(Path('a'), Path('a').join)
  utest(Path('a'), Path('a').join, [], iter(()))
  utest(Path('a/b'), Path('a').join, 'b/', [])
  utest(False, lambda: path.join() is path)
  joined_input = PathInput('b//./c/')
  joined = Path('a').join([joined_input])
  utest(Path('a/b/c'), lambda: joined)
  utest(1, lambda: joined_input.calls)
  joined_input.value = 'changed'
  utest(Path('a/b/c'), lambda: joined)

  for final in ('.', './', 'b/.', '../', 'b//./c/', 'b\\c', '\udcff'):
    for base in (Path('.'), Path('/'), Path('a')):
      utest(base / 'd' / final, base.join, ['d/'], final)
      utest(base / 'd' / final, base.join, Path('d'), [Path(final)])
  abs_input = PathInput('/b')
  utest_exc(AbsolutePathError, Path('a').join, abs_input)
  utest(1, lambda: abs_input.calls)
  for invalid, exc in (('/b', AbsolutePathError), (Path('/b'), AbsolutePathError), (PurePosixPath('/b'), AbsolutePathError),
    ('b\0c', ValueError), ('', ValueError), (PathInput(''), ValueError)):
    utest_exc(exc, Path('a').join, invalid)
    utest_exc(exc, Path('a').join, ['b', invalid])
  for invalid_type in (1, None, b'', b'b', bytearray(), memoryview(b''), BytesInput()):
    utest_exc(TypeError, Path('a').join, invalid_type)
    utest_exc(TypeError, Path('a').join, [invalid_type])
  utest_exc(TypeError, Path('a').join, [['b']])

  utest(Path('a'), lambda: Path('a/b/').parent)
  utest(Path('a'), lambda: Path('a/b').parent)
  utest(Path('.'), lambda: Path('a').parent)
  utest(Path('/'), lambda: Path('/a').parent)
  utest((Path('/a'), Path('/')), lambda: Path('/a/b/').ancestors)
  utest((), lambda: Path('.').ancestors)
  utest((Path('a'), Path('.')), lambda: Path('a/b').ancestors)
  utest_exc(ValueError, lambda: Path('.').parent)
  utest_exc(ValueError, lambda: Path('/').parent)
  utest(Path('..'), lambda: Path('../a').parent)
  utest(Path('../..'), lambda: Path('../../a/b').parent.parent)
  utest_exc(ValueError, lambda: Path('..').parent)
  utest_exc(ValueError, lambda: Path('../..').parent)
  utest((Path('../a'), Path('..')), lambda: Path('../a/b').ancestors)
  utest((), lambda: Path('..').ancestors)
  for interior in (Path('a/..'), Path('a/../b'), Path('../a/..'), Path('/..'), Path('/a/../b')):
    utest_exc(InteriorDotDotError, lambda: interior.parent)
    utest_exc(InteriorDotDotError, lambda: interior.ancestors)
    utest_exc(InteriorDotDotError, interior.has_ancestor, Path('.'))
    utest_exc(InteriorDotDotError, Path('a').has_ancestor, interior)
    utest_exc(InteriorDotDotError, interior.remove_ancestor, Path('.'))
    utest_exc(InteriorDotDotError, Path('a').remove_ancestor, interior)
    utest_exc(TypeError, interior.has_ancestor, 'a') # The type check precedes the interior check.

  utest('c', lambda: path.name)
  for named in (Path('a'), Path('a/'), Path('/a'), Path('../a'), Path('a/../b'), Path('..a')):
    utest(True, lambda: named.has_name)
  for nameless in (Path('/'), Path('.'), Path('..'), Path('../..'), Path('a/..'), Path('/..')):
    utest(False, lambda: nameless.has_name)
    for accessor in ('name', 'ext', 'exts', 'name_stem', 'stem'):
      utest_exc(ValueError, getattr, nameless, accessor)
    utest_exc(ValueError, nameless.replace_name, 'a')
    utest_exc(ValueError, nameless.replace_ext, '.x')
    utest_exc(TypeError, nameless.replace_name, 1) # The argument checks precede the name check.
    utest_exc(TypeError, nameless.replace_ext, 1)
  utest(Path('a/../c'), Path('a/../b').replace_name, 'c')
  utest(Path('a/../b.x'), Path('a/../b').replace_ext, '.x')
  utest(Path('a/b/d'), path.replace_name, 'd')
  for name in ('', '.', '..', 'a/b', 'a\0b'):
    utest_exc(ValueError, path.replace_name, name)
  utest_exc(TypeError, path.replace_name, 1)
  utest_exc(TypeError, path.replace_ext, 1)
  class StrSub(str): pass
  utest(Path('a/x'), Path('a/b').replace_name, StrSub('x'))
  utest(str, lambda: type(Path('a/b').replace_name(StrSub('x')).name))
  utest(Path('a/b.y'), Path('a/b.x').replace_ext, StrSub('.y'))
  utest(str, lambda: type(Path('a/b.x').replace_ext(StrSub('.y')).name))

  for name, ext, exts, name_stem in (
    ('a', '', (), 'a'), ('.a', '', (), '.a'), ('..a', '', (), '..a'), ('a.', '.', ('.',), 'a'),
    ('a.tar.gz', '.gz', ('.tar', '.gz'), 'a.tar'), ('.a.b', '.b', ('.b',), '.a'),
  ):
    p = Path(name)
    utest(ext, lambda: p.ext)
    utest(exts, lambda: p.exts)
    utest(name_stem, lambda: p.name_stem)
    utest(name_stem, lambda: p.stem)
    utest('/d/' + name_stem, lambda: Path('/d').join(name).stem)
    utest('../d/' + name_stem, lambda: Path('../d').join(name).stem)
  utest(Path('a.tar.zip'), Path('a.tar.gz/').replace_ext, '.zip')
  utest(Path('a.tar'), Path('a.tar.gz').replace_ext, '')
  for ext in ('x', '/x', '.a/b', '.\0x'):
    utest_exc(ValueError, path.replace_ext, ext)
  utest(Path('a.'), Path('a.b').replace_ext, '.')
  for p in (Path('a.'), Path('a.b'), Path('.a'), Path('a'), Path('a.tar.gz')):
    utest(p, lambda: p.replace_ext(p.ext))

  utest(True, Path('a/b').has_ancestor, Path('a'))
  utest(True, Path('a').has_ancestor, Path('a'))
  utest(False, Path('a').has_ancestor, Path('ab'))
  utest(False, Path('/a').has_ancestor, Path('a'))
  utest(True, Path('../a').has_ancestor, Path('..'))
  utest(False, Path('../a').has_ancestor, Path('.'))
  utest(False, Path('a').has_ancestor, Path('..'))
  utest(False, Path('../../a').has_ancestor, Path('..'))
  utest(False, Path('../a').has_ancestor, Path('../..'))
  utest(Path('a'), Path('../a').remove_ancestor, Path('..'))
  utest_exc(PathIsNotDescendantError, Path('../a').remove_ancestor, Path('.'))
  utest(Path('b'), Path('a/b').remove_ancestor, Path('a'))
  utest(Path('.'), Path('a').remove_ancestor, Path('a'))
  utest(Path('a/b'), Path('/a/b').remove_ancestor, Path('/'))
  utest_exc(PathIsNotDescendantError, Path('a').remove_ancestor, Path('b'))
  utest_exc(TypeError, Path('a').has_ancestor, 'a')

  # relative_to synthesizes `..` components.
  utest(Path('../../b/c'), Path('/a/b/c').relative_to, Path('/a/x/y'))
  utest(Path('c'), Path('a/b/c').relative_to, Path('a/b'))
  utest(Path('.'), Path('a/b').relative_to, Path('a/b/'))
  utest(Path('..'), Path('a').relative_to, Path('a/b'))
  utest(Path('../..'), Path('/').relative_to, Path('/a/b'))
  utest(Path('a/b'), Path('a/b').relative_to, Path('.'))
  utest(Path('b'), Path('../a/b').relative_to, Path('../a'))
  utest(Path('b'), Path('../b').relative_to, Path('..'))
  utest_exc(MixedAbsoluteAndRelativePathsError, Path('/a').relative_to, Path('a'))
  utest_exc(ValueError, Path('../a').relative_to, Path('a'))
  utest_exc(InteriorDotDotError, Path('a/../b').relative_to, Path('a'))
  utest_exc(InteriorDotDotError, Path('b').relative_to, Path('a/../b'))
  utest_exc(TypeError, Path('a').relative_to, 'a')

  utest(Path('a/c'), Path('a/b/../c').collapse_dotdot)
  utest(Path('a'), Path('a/b/..').collapse_dotdot)
  utest(Path('..'), Path('a/../..').collapse_dotdot)
  utest(Path('../a'), Path('../a').collapse_dotdot)
  utest(Path('/a'), Path('/../../a').collapse_dotdot)
  utest(Path('.'), Path('a/..').collapse_dotdot)
  utest(Path('/'), Path('/a/..').collapse_dotdot)
  utest(True, lambda: Path('a') == Path('a/'))
  utest(True, lambda: hash(Path('a//b')) == hash(Path('a/b')))
  utest(True, lambda: Path('.') == Path('./'))
  utest((Path('.'), Path('a'), Path('a/b'), Path('a-x'), Path('/')),
    lambda: tuple(sorted((Path('/'), Path('a-x'), Path('a/b'), Path('a'), Path('.')))))
  for lesser, greater in ((Path('.'), Path('a')), (Path('a'), Path('a/b')), (Path('a/b'), Path('a-x')), (Path('b'), Path('/'))):
    utest((True, True, False, False), lambda: (lesser < greater, lesser <= greater, lesser > greater, lesser >= greater))
    utest((False, False, True, True), lambda: (greater < lesser, greater <= lesser, greater > lesser, greater >= lesser))
    utest((False, True, False, True), lambda: (lesser < lesser, lesser <= lesser, lesser > lesser, lesser >= lesser))
  for op in (lt, le, gt, ge):
    utest_exc(TypeError, op, Path('a'), 'a')
    utest_exc(TypeError, op, 'a', Path('a'))

  samples = ('.', './', './.', '/', '//', '/.', 'a', 'a/', 'a/.', 'a/./', 'a/./.', 'a//b/./c/',
    '/a/..', '../a', 'a\\b', '~', 'a\n', '\udcff')
  for sample in samples:
    p = Path(sample)
    utest(p, Path, str(p))
    utest(hash(p), hash, Path(str(p)))
    c = p.collapse_dotdot() # Ancestry operations reject interior `..`.
    for base in (Path('.'), Path('/'), Path('a')):
      if c.has_ancestor(base): utest(c, lambda: base / c.remove_ancestor(base))
      else: utest_exc(PathIsNotDescendantError, c.remove_ancestor, base)
