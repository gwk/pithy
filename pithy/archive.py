# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from functools import total_ordering
from io import BytesIO, TextIOBase, TextIOWrapper
from typing import Any, BinaryIO, Callable, Iterable, List, Tuple, Union
from tarfile import TarFile
from zipfile import ZipFile, BadZipFile
from .fs import path_ext
from .util import lazy_property
from .io import *


FileOrPath = Union[BinaryIO, str] # TODO: support other pathlike objects.
Opener = Callable[[], BinaryIO]


class Archive:

  def __init__(self, file_or_path:FileOrPath, ext=None) -> None:
    self.name: str = getattr(file_or_path, 'name', str(file_or_path))
    if ext is None:
      ext = path_ext(self.name)
    self.ext = ext
    try: self._handler = _ext_handlers[ext](file_or_path)
    except KeyError: raise ValueError(f'Archive does not support extension: {ext!r}')


  def __repr__(self) -> str:
    return f'{self.__class__.__name__}(name={self.name!r})'


  def __iter__(self) -> Iterable['ArchiveFile']:
    return self._handler.files(self)



@total_ordering
class ArchiveMember:

  def __init__(self, archive: Archive, name: str) -> None:
    self.archive = archive
    self.name = name

  def __repr__(self) -> str:
    return f'{self.__class__.__name__}({self.archive}, {self.name!r})'

  def __lt__(self, other: Any) -> bool:
    if isinstance(other, ArchiveMember):
      return self.name < other.name
    return NotImplemented



class ArchiveFile(ArchiveMember):

  def __init__(self, archive:Archive, name:str, opener:Opener) -> None:
    super().__init__(archive=archive, name=name)
    self._opener = opener

  @lazy_property
  def _file(self): return self._opener()

  def __iter__(self): return iter(self._file)

  def __getattr__(self, name):
    # note: dunder attribute access is never forwarded to this method.
    if name.startswith('_'): raise AttributeError(name)
    return getattr(self._file, name)

  def seekable(self):
    return getattr(self._file, 'seekable', False)

  def text(self, encoding='UTF-8', errors=None, newline=None) -> TextIOWrapper:
    'Returns a TextIOWrapper around the underlying binary buffer.'
    return TextIOWrapper(self._file, encoding=encoding, errors=errors, newline=newline)



class ArchiveDir(ArchiveMember): pass


class _Handler:
  def __init__(self, file_or_path:FileOrPath) -> None: raise NotImplementedError()


class _TarHandler(_Handler):
  def __init__(self, file_or_path:FileOrPath) -> None:
    self.tar = TarFile.open(mode='r|*', fileobj=file_or_path)

  def files(self, archive:Archive) -> Iterable[Tuple[str, Opener]]:
    for info in self.tar:
      if info.isdir(): continue
      opener = lambda: self.tar.extractfile(info)
      #^ note: crucial to pass info here and not name, or else gz archives get very slow.
      yield ArchiveFile(archive=archive, name=info.name, opener=opener)


class _ZipHandler(_Handler):
  def __init__(self, file_or_path:FileOrPath) -> None:
    try: self.zip = ZipFile(file_or_path)
    except BadZipFile as e:
      if isinstance(file_or_path, TextIOBase):
        raise TypeError(f'Archive requires a path or binary stream but received text stream: {file_or_path}') from e
      raise

  def files(self, archive:Archive) -> Iterable[Tuple[str, Opener]]:
    for name in self.zip.namelist():
      if name.endswith('/'): continue # directory.
      opener = lambda: self.zip.open(name)
      yield ArchiveFile(archive=archive, name=name, opener=opener)


_ext_handlers = {
  '.bz2' : _TarHandler,
  '.gz'  : _TarHandler,
  '.tar' : _TarHandler,
  '.xz', : _TarHandler,
  '.zip' : _ZipHandler,
}
