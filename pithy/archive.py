# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from functools import total_ordering
from io import TextIOBase, TextIOWrapper
from tarfile import TarFile
from typing import Any, BinaryIO, Callable, Dict, Iterable, List, Type, Union, cast
from zipfile import BadZipFile, ZipFile

from .fs import path_ext
from .util import lazy_property


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

  @property
  def file_names(self) -> List[str]: return self._handler.file_names



@total_ordering
class ArchiveMember:

  def __init__(self, archive: Archive, name: str) -> None:
    self.archive = archive
    self.name = name

  def __repr__(self) -> str:
    return f'{self.__class__.__name__}({self.archive}, {self.name!r})'

  def __lt__(self, other: Any) -> Union[bool, 'NotImplemented']:
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

  def __init__(self, file_or_path:FileOrPath) -> None: raise NotImplementedError

  def files(self, archive:Archive) -> Iterable[ArchiveFile]: raise NotImplementedError

  @property
  def file_names(self) -> List[str]: raise NotImplementedError


class _TarHandler(_Handler):
  def __init__(self, file_or_path:FileOrPath) -> None:
    if isinstance(file_or_path, str):
      file_or_path = open(file_or_path, 'rb')
    self.tar = TarFile.open(mode='r|*', fileobj=file_or_path)

  def files(self, archive:Archive) -> Iterable[ArchiveFile]:
    for info in self.tar:
      if info.isdir(): continue
      def opener() -> BinaryIO:
        f = self.tar.extractfile(info)
        if f is None: raise Exception(f'archive failed to open file: {info.name}')
        return cast(BinaryIO, f)
      #^ note: crucial to pass info here and not name, or else gz archives get very slow.
      yield ArchiveFile(archive=archive, name=info.name, opener=opener)

  @property
  def file_names(self) -> List[str]: return self.tar.getnames()



class _ZipHandler(_Handler):
  def __init__(self, file_or_path:FileOrPath) -> None:
    try: self.zip = ZipFile(file_or_path)
    except BadZipFile as e:
      if isinstance(file_or_path, TextIOBase):
        raise TypeError(f'Archive requires a path or binary stream but received text stream: {file_or_path}') from e
      raise

  def files(self, archive:Archive) -> Iterable[ArchiveFile]:
    for name in self.file_names:
      if name.endswith('/'): continue # directory.
      def opener() -> BinaryIO: return cast(BinaryIO, self.zip.open(name, 'r')) # mypy bug: BinaryIO and IO[bytes] should be equivalent.
      yield ArchiveFile(archive=archive, name=name, opener=opener)

  @property
  def file_names(self) -> List[str]: return self.zip.namelist()



_ext_handlers: Dict[str, Type[_Handler]] = {
  '.bz2' : _TarHandler,
  '.gz'  : _TarHandler,
  '.tar' : _TarHandler,
  '.xz'  : _TarHandler,
  '.zip' : _ZipHandler,
}
