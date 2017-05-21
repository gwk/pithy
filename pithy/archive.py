# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from functools import total_ordering
from io import TextIOBase, TextIOWrapper
from typing import Any, BinaryIO, Iterable, Tuple, Union, IO
from zipfile import ZipFile, BadZipFile
from .util import lazy_property


class Archive:

  def __init__(self, file_or_path:Union[BinaryIO, str]) -> None:
    self.name: str = getattr(file_or_path, 'name', str(file_or_path))
    try: self.zip_file = ZipFile(file_or_path)
    except BadZipFile as e:
      if isinstance(file_or_path, TextIOBase):
        raise TypeError(f'ZipFile requires a path or binary stream but received text stream: {file_or_path}') from e
      raise


  def __repr__(self) -> str:
    return f'{self.__class__.__name__}(name={self.name!r})'


  @lazy_property
  def names(self) -> Tuple[str, ...]:
    return tuple(self.zip_file.namelist())


  @lazy_property
  def file_names(self) -> Tuple[str, ...]:
    return tuple(n for n in self.names if not n.endswith('/'))


  def __iter__(self) -> Iterable['ArchiveFile']:
    for name in self.file_names:
      yield ArchiveFile(archive=self, name=name)



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
    raise TypeError(f"'<' not supported between {self!r} and {other!}")


class ArchiveFile(ArchiveMember):

  def __init__(self, archive: Archive, name: str) -> None:
    super().__init__(archive=archive, name=name)

  @lazy_property
  def _zip_file(self): return self.archive.zip_file.open(self.name)

  def __iter__(self): return iter(self._zip_file)

  def __getattr__(self, name):
    if name.startswith('_'): raise AttributeError(name)
    return getattr(self._zip_file, name)

  def text(self, encoding='UTF-8', errors=None, newline=None) -> TextIOWrapper:
    '''
    Obtain a TextIOWrapper around the underlying binary buffer.
    '''
    return TextIOWrapper(self._zip_file, encoding=encoding, errors=errors, newline=newline)



class ArchiveDir(ArchiveMember): pass
