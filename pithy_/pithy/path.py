# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re as _re
from collections.abc import Buffer, Iterable
from os import fspath as _fspath, PathLike
from os.path import (basename as _basename, commonpath as _commonpath, dirname as _dirname, expanduser as _expand_user,
  isabs as _isabs, join as _join, realpath as _realpath, relpath as _relpath, split as _split)
from typing import Self


'''
The path module defines those operations on paths that are pure string operations.
For path operations that require systems calls, see pithy.filestatus and pithy.fs.

Terminology, for the path `d/s.e`:
* `dir`/`parent`: `d`, the path minus its final component.
* `name`: `s.e`, the final component.
* `ext`: `.e`, the final extension, including the dot.
* `stem`: `d/s`, the path minus its final extension.
* `name_stem`: `s`, the name minus its final extension.

Thus `stem` means the path sans its extension, and the `name_` prefix restricts a term to the final component.
Note that this differs from `pathlib`, where `stem` denotes what is here called `name_stem`, and `suffix` denotes `ext`.
'''

_context_keywords_ = ['PathLike', 'PurePath', 'ancestor', 'basename', 'components', 'directory', 'dirname', 'extension', 'join',
  'lexical', 'normalize', 'os.path', 'pathlib', 'relative path', 'splitext', 'stem', 'suffix']


type Pathish = str|PathLike
type PathishOrFd = Pathish|int


_setattr = object.__setattr__


class AbsolutePathError(ValueError): pass
class InteriorDotDotError(ValueError): pass
class MixedAbsoluteAndRelativePathsError(ValueError): pass
class NotAPathError(ValueError): pass
class PathIsNotDescendantError(ValueError): pass


def _dotdot_prefix_len(parts:tuple[str,...]) -> int:
  'Count the leading `..` components.'
  n = 0
  for part in parts:
    if part != '..': break
    n += 1
  return n


def _has_name(parts:tuple[str,...]) -> bool:
  'A path with no components, or whose final component is `..`, has no name.'
  return bool(parts) and parts[-1] != '..'


def _parse_path_str(pathlike:str|PathLike[str], require_rel:bool=False) -> tuple[tuple[str,...],bool]:
  '''
  Parse a str or PathLike into normalized components and an absolute flag.
  This is the single definition of Path's lexical rules; see the class docstring.
  `require_rel` raises AbsolutePathError for an absolute path, here so that `__fspath__` is called exactly once.
  '''
  s = _fspath(pathlike)
  if not isinstance(s, str): raise TypeError(f'Path requires a str path; received {type(s).__name__}.')
  s = str.__str__(s) # Copy a str subclass to avoid calling its overridden methods while parsing.
  if not s: raise ValueError('Path cannot be empty.')
  if '\0' in s: raise ValueError('Path cannot contain NUL.')
  is_abs = s.startswith('/')
  if require_rel and is_abs: raise AbsolutePathError(f'Cannot join absolute path: {s}')
  return tuple(part for part in s.split('/') if part and part != '.'), is_abs


class Path:
  '''
  An immutable POSIX path manipulated without filesystem access.

  This class is "lexical" in the same sense as `pathlib.PurePath`: operations work on path components without consulting
  the filesystem, checking existence, or resolving symlinks.

  Parsing drops empty and dot components, and so drops a trailing slash or a final `/.`: `Path('x/')` and `Path('x/.')`
  both render as `x`. A path therefore does not record whether it names a directory; that is a property of the filesystem.
  Where a system call must distinguish the two, use `str_with_slash` at the call site.
  The empty string is rejected, because POSIX rejects the empty pathname; `Path()` defaults to `'.'`.
  A path with no components renders as `.` or, when absolute, `/`.
  Consequently `.` is the identity element of `join`: `Path('x') / '.'` is `Path('x')`.

  The anchor of an absolute path is the root; the anchor of a relative path is its leading run of `..` components, or `.`
  when there is none. The ancestry operations `parent`, `ancestors`, `has_ancestor` and `remove_ancestor` stop at the anchor.
  They raise InteriorDotDotError for a `..` component that follows an ordinary component, or any `..` in an absolute path,
  because a lexical answer would then misstate the location; call `collapse_dotdot` first to accept its caveats explicitly.
  `relative_to` is the one operation that synthesizes `..` components; it carries the same caveat.

  A path with no components, or whose final component is `..`, has no name. For such paths `name`, `ext`, `exts`,
  `name_stem` and `stem` raise ValueError rather than returning an empty string that could pass silently into further
  string operations; test `has_name` first when the input may include them.

  Python's Unix filesystem APIs use surrogateescape for undecodable filename bytes; Path preserves those characters.

  `parts`: Normalized components without separators.
  `is_abs`: Whether the path begins at the POSIX root.

  Equality, hashing and ordering compare both fields, so `Path('a')` and `Path('a/')` are the same dict and set key.
  '''

  __slots__ = ('parts', 'is_abs')

  parts:tuple[str,...]
  is_abs:bool


  def __init_subclass__(cls, **kwargs:object) -> None:
    'Disallow subclasses so equality and returned types remain fixed.'
    raise TypeError('Path cannot be subclassed.')


  def __init__(self, pathlike:str|PathLike[str]='.') -> None:
    'Parse a string path or the string result of a path-like object.'

    if hasattr(self, 'parts'): raise AttributeError('Path is immutable; calling `__init__` on an instance is prohibited.')

    parts, is_abs = _parse_path_str(pathlike)
    _setattr(self, 'parts', parts)
    _setattr(self, 'is_abs', is_abs)


  @classmethod
  def _from_parts(cls, parts:tuple[str,...], is_abs:bool) -> Self:
    'Build a path from normalized components without parsing again.'
    path = object.__new__(cls)
    _setattr(path, 'parts', parts)
    _setattr(path, 'is_abs', is_abs)
    return path


  def __setattr__(self, name:str, value:object) -> None:
    'Reject attribute changes after construction.'
    raise AttributeError('Path is immutable.')


  def __delattr__(self, name:str) -> None:
    'Reject attribute deletion.'
    raise AttributeError('Path is immutable.')


  def __str__(self) -> str:
    'Render the path using this class\'s normalized spelling.'
    if not self.parts: return '/' if self.is_abs else '.'
    return ('/' if self.is_abs else '') + '/'.join(self.parts)


  def __repr__(self) -> str:
    'Render a reconstructible expression.'
    return f'Path({str(self)!r})'


  def str_with_slash(self) -> str:
    '''
    Render the path with a trailing slash, which asserts to the system that the path names a directory.
    A trailing slash makes `rename`, `rmdir` and `open` fail on a non-directory, and some tools such as `rsync` use it to
    mean the contents of a directory rather than the directory itself.
    Path does not record a trailing slash, so this is the place to add one. The root is unchanged.
    '''
    s = str(self)
    return s if s == '/' else s + '/'


  def __fspath__(self) -> str:
    'Return the rendered path, so that Path is accepted by `os.fspath` and the standard filesystem APIs.'
    return str(self)


  def __reduce__(self) -> tuple[type[Self],tuple[str]]:
    '''
    Pickle as the rendered string, so that reconstruction runs the constructor rather than setting attributes.
    The default protocol fills slots with `setattr` after `__new__`, which the immutability guard rejects.
    '''
    return (type(self), (str(self),))


  def __copy__(self) -> Self:
    'Return self; an immutable path never needs copying.'
    return self


  def __deepcopy__(self, memo:dict[int,object]) -> Self:
    'Return self; an immutable path never needs copying.'
    return self


  def __eq__(self, other:object) -> bool:
    'Compare anchors and components.'
    if type(other) is not Path: return NotImplemented
    return self._order_key == other._order_key


  def __hash__(self) -> int:
    'Hash the same fields used for equality.'
    return hash(self._order_key)


  @property
  def _order_key(self) -> tuple[bool,tuple[str,...]]:
    'The tuple used for equality, hashing, and ordering.'
    return (self.is_abs, self.parts)


  def __lt__(self, other:Self) -> bool:
    '''
    Order paths by anchor, then component-wise; relative paths precede absolute ones.
    Component-wise ordering keeps a directory's contents together, and differs from ordering the rendered strings:
    `a/b` precedes `a-x`, although the character `-` precedes `/`.
    '''
    if type(other) is not Path: return NotImplemented
    return self._order_key < other._order_key


  def __le__(self, other:Self) -> bool:
    'See `__lt__`.'
    if type(other) is not Path: return NotImplemented
    return self._order_key <= other._order_key


  def __gt__(self, other:Self) -> bool:
    'See `__lt__`.'
    if type(other) is not Path: return NotImplemented
    return self._order_key > other._order_key


  def __ge__(self, other:Self) -> bool:
    'See `__lt__`.'
    if type(other) is not Path: return NotImplemented
    return self._order_key >= other._order_key


  def __truediv__(self, other:str|PathLike[str]) -> Self:
    '''
    Join one relative path using `join` semantics; reject an absolute right operand.
    Note that `__rtruediv__` is intentionally not implemented, for simplicity and clarity: the left operand must be a Path.
    '''
    if not isinstance(other, (str, PathLike, Path)): return NotImplemented
    return self.join(other)


  @property
  def has_name(self) -> bool:
    'Whether the path has a final component that is a name, which excludes the anchors and a final `..`.'
    return _has_name(self.parts)


  @property
  def name(self) -> str:
    'Return the final component. Raise ValueError if the path has no name.'
    if not self.has_name: raise ValueError(f'Path has no name: {self!s}')
    return self.parts[-1]


  @property
  def _anchor_len(self) -> int:
    'The number of leading components that belong to the anchor; see the class docstring.'
    return 0 if self.is_abs else _dotdot_prefix_len(self.parts)


  def _check_no_interior_dotdot(self) -> None:
    'Raise InteriorDotDotError if a `..` component lies beyond the anchor.'
    if '..' in self.parts[self._anchor_len:]:
      raise InteriorDotDotError(f'Path has an interior `..` component; collapse_dotdot first: {self!s}')


  @property
  def parent(self) -> Self:
    'Return the immediate parent. Raise ValueError at the anchor and InteriorDotDotError for an interior `..`.'
    self._check_no_interior_dotdot()
    if len(self.parts) <= self._anchor_len: raise ValueError(f'Path has no parent: {self!s}')
    return self._from_parts(self.parts[:-1], self.is_abs)


  @property
  def ancestors(self) -> tuple[Self,...]:
    'Return all ancestors from the immediate parent to the anchor. Raise InteriorDotDotError for an interior `..`.'
    self._check_no_interior_dotdot()
    indices = range(len(self.parts) - 1, self._anchor_len - 1, -1)
    return tuple(self._from_parts(self.parts[:i], self.is_abs) for i in indices)


  @property
  def ext(self) -> str:
    'Return the final extension of the name, ignoring leading dots. Raise ValueError if the path has no name.'
    name = self.name
    dot = name.rfind('.')
    return name[dot:] if dot >= len(name) - len(name.lstrip('.')) else ''


  @property
  def exts(self) -> tuple[str,...]:
    '''
    Return all extensions of the name, ignoring leading dots. Raise ValueError if the path has no name.
    `a.tar.gz` yields `('.tar', '.gz')` and `.bashrc` yields `()`. A repeated dot yields a bare `.`: `a..b` gives `('.', '.b')`.
    '''
    name = self.name
    sans_leading_dots = name.lstrip('.')
    dot = sans_leading_dots.find('.')
    if dot == -1: return ()
    return tuple('.' + part for part in sans_leading_dots[dot + 1:].split('.'))


  @property
  def name_stem(self) -> str:
    'Return the name without its final extension. Raise ValueError if the path has no name.'
    ext = self.ext
    return self.name[:-len(ext)] if ext else self.name


  @property
  def stem(self) -> str:
    'Return the rendered path without its final extension. Raise ValueError if the path has no name.'
    ext = self.ext
    path = str(self)
    return path[:-len(ext)] if ext else path


  def replace_name(self, name:str) -> Self:
    'Replace the final component with a valid name. Raise ValueError if the path has no name.'
    if not isinstance(name, str): raise TypeError(f'Path name requires a str; received {type(name).__name__}.')
    name = str.__str__(name) # Copy a str subclass, as in __init__.
    if not name or name in ('.', '..') or '/' in name or '\0' in name: raise ValueError(f'Invalid path name: {name!r}')
    if not self.has_name: raise ValueError(f'Path has no name: {self!s}')
    return self._from_parts(self.parts[:-1] + (name,), self.is_abs)


  def replace_ext(self, ext:str) -> Self:
    '''
    Replace the final extension. An empty extension removes it. Raise ValueError if the path has no name.
    A bare `.` is accepted, because `ext` returns `.` for a name such as `a.`; thus `p.replace_ext(p.ext) == p`.
    '''
    if not isinstance(ext, str): raise TypeError(f'Path extension requires a str; received {type(ext).__name__}.')
    ext = str.__str__(ext) # Copy a str subclass, as in __init__.
    if ext and (not ext.startswith('.') or '/' in ext or '\0' in ext):
      raise ValueError(f'Invalid path extension: {ext!r}')
    return self.replace_name(self.name_stem + ext)


  def has_ancestor(self, ancestor:Self) -> bool:
    '''
    Test whether the components of `ancestor` are a prefix of this path's components, with the same anchor.
    This is a whole-component comparison: `ab` does not have the ancestor `a`.
    A path counts as its own ancestor. Raise InteriorDotDotError if either path has an interior `..`.
    '''
    if type(ancestor) is not Path: raise TypeError('Expected a Path.')
    self._check_no_interior_dotdot()
    ancestor._check_no_interior_dotdot()
    return (self.is_abs == ancestor.is_abs and self._anchor_len == ancestor._anchor_len
      and self.parts[:len(ancestor.parts)] == ancestor.parts)


  def remove_ancestor(self, ancestor:Self) -> Self:
    '''
    Remove the leading components matched by `has_ancestor`, without synthesizing `..` components.
    The result is relative, and rejoining it to `ancestor` reproduces this path.
    Raise PathIsNotDescendantError otherwise, or InteriorDotDotError as `has_ancestor` does.
    '''
    if not self.has_ancestor(ancestor): raise PathIsNotDescendantError(f'{ancestor!s} is not an ancestor of {self!s}.')
    return self._from_parts(self.parts[len(ancestor.parts):], False)


  def relative_to(self, start:Self) -> Self:
    '''
    Return the relative path that leads from the directory `start` to this path, synthesizing `..` components as needed.
    The result is `.` when the two paths are equal.
    Both paths must share an anchor: both absolute, or both relative with the same leading `..` components,
    because the location of one relative to the other is otherwise unknown.
    Raise MixedAbsoluteAndRelativePathsError or ValueError for differing anchors, and InteriorDotDotError as `has_ancestor` does.
    The result is lexical: if a component of `start` is a symlink, the system resolves `..` through the link target,
    and the result can then name a different location. Use `fs.path_rel_to_dir` to resolve relative inputs first.
    '''
    if type(start) is not Path: raise TypeError('Expected a Path.')
    if self.is_abs != start.is_abs: raise MixedAbsoluteAndRelativePathsError((self, start))
    self._check_no_interior_dotdot()
    start._check_no_interior_dotdot()
    anchor_len = self._anchor_len
    if anchor_len != start._anchor_len: raise ValueError(f'Paths have different anchors: {self!s}; {start!s}')
    common = anchor_len
    for a, b in zip(self.parts[anchor_len:], start.parts[anchor_len:]):
      if a != b: break
      common += 1
    ups = ('..',) * (len(start.parts) - common)
    return self._from_parts(ups + self.parts[common:], False)


  def join(self, *paths:str|PathLike[str]|Iterable[str|PathLike[str]]) -> Self:
    '''
    Join relative paths and iterables of relative paths, expanding iterables one level, without intermediate Path objects.
    Reject absolute additions. With no paths, return a new copy; empty iterables and dot paths have no effect.
    '''
    parts = list(self.parts)
    for arg in paths:
      if isinstance(arg, (str, PathLike)): items:Iterable[object] = (arg,)
      elif isinstance(arg, Iterable) and not isinstance(arg, Buffer): items = arg
      else: raise TypeError(f'Path.join requires str, PathLike, or an iterable of those; received {type(arg).__name__}.')
      for path in items:
        if isinstance(path, Path):
          if path.is_abs: raise AbsolutePathError(f'Cannot join absolute path: {path!s}')
          parts.extend(path.parts)
        elif isinstance(path, (str, PathLike)):
          next_parts, _ = _parse_path_str(path, require_rel=True)
          parts.extend(next_parts)
        else: raise TypeError(f'Path.join requires str or PathLike elements; received {type(path).__name__}.')
    return self._from_parts(tuple(parts), self.is_abs)


  def collapse_dotdot(self) -> Self:
    '''
    Collapse `..` components without consulting the filesystem. Symlinks can make the result refer to a different location.
    Even without symlinks, `missing/../file` becomes `file`: the original lookup fails if `missing` does not exist,
    while the collapsed path can succeed because it no longer requires that directory.
    '''
    parts:list[str] = []
    for part in self.parts:
      if part == '..':
        if parts and parts[-1] != '..': parts.pop()
        elif not self.is_abs: parts.append(part)
      else: parts.append(part)
    return self._from_parts(tuple(parts), self.is_abs)


def executable_dir() -> str:
  'Return the parent directory of this excutable.'
  return _dirname(executable_path())


def executable_path() -> str:
  'Return the path to this executable.'
  import __main__
  path = __main__.__file__
  if not path: raise Exception('could not determine executable path.')
  return _realpath(path)


def expand_home_dir(path:Pathish) -> str:
  return _expand_user(path)


def insert_path_stem_suffix(path:Pathish, suffix:str) -> str:
  'Insert a suffix in between the path stem and ext.'
  stem, ext = split_stem_ext(path)
  return f'{stem}{suffix}{ext}'


def is_norm_path(path:Pathish) -> bool:
  return bool(_norm_path_re.fullmatch(str_path(path)))


_norm_path_re = _re.compile(r'''(?x)
# This is nasty. In particular the "component" clauses have to deal with the validity of three or more dots.
  [./] # Either a lone dot or slash, or...
| (?: # Absolute path.
    / # Leading slash.
    (?:[^./]|\.{1,2}[^./]|\.{3})[^/]* # Component.
  )+
| # Relative path.
  (?: \.\./ )* # Leading backups ending with a slash.
  (?:
    \.\. # Final backup.
  | (?:[^./]|\.{1,2}[^./]|\.{3})[^/]* # Initial component.
    (?: / (?:[^./]|\.{1,2}[^./]|\.{3})[^/]* )* # Trailing components.
  )
''')


def is_path_abs(path:Pathish) -> bool:
  'Return true if `path` is an absolute path.'
  return _isabs(path)


def is_sub_path(path:Pathish) -> bool:
  'Return true if `path` is a relative path that, after normalization, does not refer to parent directories.'
  return not is_path_abs(path) and '..' not in path_split(path)



def norm_path(path:Pathish) -> str:
  '''
  Normalize `path`.
  * Empty string is treated as '.'.
  * trailing slashes are removed.
  * duplicate slashes (empty components) and '.' components are removed.
  * '..' components are simplified, or dropped if it implies a location beyond the root '/'.
  * Unlike `os.path.normpath`, this implementation simplifies leading double slash to a single slash.
  '''
  p = str_path(path)
  lead_slash = '/' if p.startswith('/') else ''
  comps:list = []
  for comp in p.split('/'):
    if not comp or comp == '.': continue
    if comp == '..':
      if comps:
        if comps[-1] == '..': comps.append(comp)
        else: comps.pop()
      else:
        if lead_slash: pass # '..' beyond root gets dropped.
        else: comps.append(comp)
    else:
      comps.append(comp)
  return (lead_slash + '/'.join(comps)) or '.'


def path_common_prefix(*paths:Pathish) -> str:
  'Return the common path prefix for a sequence of paths.'
  try: return _commonpath([str_path(p) for p in paths])
  except ValueError: # we want a more specific exception.
    raise MixedAbsoluteAndRelativePathsError(paths) from None


def path_compound_ext(path:Pathish) -> str:
  return ''.join(path_exts(path))


def path_descendants(start_path:Pathish, end_path:Pathish, *, include_start:bool=True, include_end:bool=True) -> tuple[str, ...]:
  '''
  Return a tuple of paths from `start_path` to `end_path`.
  By default, `include_start` and `include_end` are both True.
  '''
  prefix = path_split(norm_path(start_path))
  comps = path_split(norm_path(end_path))
  assert prefix
  assert comps
  if prefix[0].startswith('..') or comps[0].startswith('..'):
    raise ValueError(f"'..' dir components in end_path are not supported: {end_path!r}")
  if prefix == comps:
    return (str_path(start_path),) if include_start or include_end else ()
  if prefix != comps[:len(prefix)]:
    raise PathIsNotDescendantError(end_path, start_path)
  start_i = len(prefix) + (0 if include_start else 1)
  end_i = len(comps) + (1 if include_end else 0)
  return tuple(path_join(*comps[:i]) for i in range(start_i, end_i))


def path_dir(path:Pathish) -> str:
  "Return the dir portion of `path` (possibly empty), e.g. 'dir/name'."
  return _dirname(str_path(path))


def path_dir_or_dot(path:Pathish) -> str:
  "Return the dir portion of a path, e.g. 'dir/name', or '.' in the case of no path."
  return path_dir(path) or '.'


def path_ext(path:Pathish) -> str:
  'The file extension of the path.'
  return split_stem_ext(path)[1]


def path_exts(path:Pathish) -> tuple[str, ...]:
  exts = []
  while True:
    path, ext = split_stem_ext(path)
    if not ext: break
    exts.append(ext)
  exts.reverse()
  return tuple(exts)


def path_join(first:Pathish, *subsequent:Pathish) -> str:
  '''
  Join the paths using the system path separator.
  Unlike `os.path.join`, this implementation does not allow subsequent absolute paths to replace the preceding path.
  Currently it does not allow absolute paths at all.
  TODO: perhaps we should join subsequent absolute paths as if they were relative?
  '''
  for p in subsequent:
    if is_path_abs(p): raise AbsolutePathError(p)
  return _join(str_path(first), *[str_path(p) for p in subsequent])


def path_name(path:Pathish) -> str:
  "Return the name portion of a path (possibly including an extension); the 'basename' in Unix terminology."
  return _basename(str_path(path))


def path_name_stem(path:Pathish) -> str:
  'The file name without the final extension; the name stem will not span directories.'
  return path_stem(path_name(path))


def path_name_stem_sans_exts(path:Pathish) -> str:
  'The file name without any extensions; the name stem will not span directories.'
  return path_stem_sans_exts(path_name(path))


def path_rel_to_ancestor(path:Pathish, ancestor:str, dot:bool=False) -> str:
  '''
  Return the path relative to `ancestor`.
  If `path` is not descended from `ancestor`, raise PathIsNotDescendantError.
  If `path` and `ancestor` are equivalent (path component-wise),
   then return '.' if dot is True, or else raise PathIsNotDescendantError.
  '''
  comps = path_split(path)
  prefix = path_split(ancestor)
  if comps == prefix:
    if dot: return '.'
    raise PathIsNotDescendantError(path, ancestor)
  if prefix == comps[:len(prefix)]:
    return path_join(*comps[len(prefix):])
  raise PathIsNotDescendantError(path, ancestor)


def path_split(path:Pathish) -> list[str]:
  # TODO: rename to path_comps?
  np = norm_path(path)
  if np == '/': return ['/']
  assert not np.endswith('/')
  return [comp or '/' for comp in np.split('/')]


def path_stem(path:Pathish) -> str:
  'The path without the final file extension; the stem may span multiple directories.'
  return split_stem_ext(path)[0]


def path_stem_sans_exts(path:Pathish) -> str:
  'The path without any file extensions; the stem may span multiple directories.'
  return split_stem_multi_ext(path)[0]


def rel_path(path:Pathish, start:Pathish='.') -> str:
  'Return a version of `path` relative to `start`, which defaults to the current directory.'
  return _relpath(str_path(path), str_path(start))


def replace_first_dir(path:Pathish, replacement:str) -> str:
  parts = path_split(path)
  if not parts: raise Exception('replace_first_dir: path is empty')
  parts[0] = replacement
  return path_join(*parts)


def split_dir_name(path:Pathish) -> tuple[str, str]:
  "Split the path into dir and name (possibly including an extension) components, e.g. 'dir/name'."
  return _split(str_path(path))


def split_dir_stem_ext(path:Pathish) -> tuple[str, str, str]:
  'Split the path into a (dir, stem, ext) triple.'
  dir, name = split_dir_name(path)
  stem, ext = split_stem_ext(name)
  return dir, stem, ext


def split_stem_ext(path:Pathish) -> tuple[str, str]:
  '''
  Split `path` into (stem, extension) components.
  'stem.ext' -> ('stem', '.ext').
  'stem.ext.ext' -> ('stem.ext', '.ext').
  The stem can include slashes. The extension may be empty.
  Extension is everything from the last dot to the end, ignoring leading dots in the file name.
  It is always true that `path == root + ext`.
  '''
  path = str_path(path)
  slash_idx = path.rfind('/') # -1 if not found.
  dot_idx = path.rfind('.') # -1 if not found.
  if slash_idx < dot_idx: # Found a dot after the last slash, if any slash exists. Skip all leading dots in the name.
    name_idx = slash_idx + 1 # Start of the file name.
    while name_idx < dot_idx:
      if path[name_idx] != '.': # Found a non-dot character in the name.
        return path[:dot_idx], path[dot_idx:]
      name_idx += 1 # Skip the dot.
  return path, ''


def split_stem_multi_ext(path:Pathish) -> tuple[str, str]:
  '''
  Split `path` into (stem, multi-extension) components.
  'stem.ext' -> ('stem', '.ext').
  'stem.ext.ext' -> ('stem', '.ext.ext').
  The stem can include slashes. The extension may be empty.
  The multi-extension is everything from the first dot in the file name to the end, ignoring leading dots in the file name.
  It is always true that `path == root + ext`.
  '''
  path = str_path(path)
  slash_idx = path.rfind('/') # -1 if not found.
  name_idx = slash_idx + 1 # Start of the file name.
  dot_find_start_idx = name_idx
  while dot_find_start_idx < len(path) and path[dot_find_start_idx] == '.': # Skip leading dots in the file name.
    dot_find_start_idx += 1
  dot_idx = path.find('.', dot_find_start_idx)
  if dot_idx == -1: return path, ''
  return path[:dot_idx], path[dot_idx:]


def str_path(path:Pathish) -> str:
  p = _fspath(path)
  if isinstance(p, str): return p
  assert isinstance(p, bytes)
  return p.decode()


def vscode_path(path:str) -> str:
  'VSCode will only recognize source locations if the path contains a slash; add "./" to plain file names.'
  if '/' in path or path.startswith('<') and path.endswith('>'): return path # Do not alter pseudo-names like <stdin>.
  return './' + path
