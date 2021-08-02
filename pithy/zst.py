from typing import IO, AnyStr, BinaryIO, Iterable, Iterator, List, TextIO

from zstandard import ZstdCompressor

from .typing import OptBaseExc, OptTraceback, OptTypeBaseExc


class ZstWriterBase(IO[AnyStr]):

  def __init__(self, file:BinaryIO, level=6, threads=1, chunk_size=32768) -> None:
    self.file = file
    self.compressor = ZstdCompressor(level=level, threads=1)
    self.chunker = self.compressor.chunker(chunk_size=chunk_size)
    # TODO: use stream_writer instead of chunker?
    #stream_writer = cctx.stream_writer(fh)
    self.input_byte_count = 0
    self.compressed_byte_count = 0

  def __iter__(self) -> Iterator[AnyStr]: raise TypeError

  def __next__(self) -> AnyStr: raise TypeError

  def fileno(self) -> int: return self.file.fileno()

  def isatty(self) -> bool: return self.file.isatty()

  def readable(self) -> bool: return self.file.readable()

  def writable(self) -> bool: return self.file.writable()

  def tell(self) -> int: return self.file.tell()

  def truncate(self, size:int=None) -> int: return self.file.truncate()

  def read(self, size=-1) -> AnyStr: raise TypeError

  def readline(self, size=-1) -> AnyStr: raise TypeError

  def readlines(self, size=-1) -> List[AnyStr]: raise TypeError

  def seek(self, offset:int, whence=0) -> int: return self.file.seek(offset, whence)

  def seekable(self) -> bool: return self.file.seekable()


  def writelines(self, lines:Iterable) -> None:
    for line in lines: self.write(line)

  def _write_chunks(self, chunks:Iterable[bytes]) -> None:
    for chunk in chunks:
      self.compressed_byte_count += self.file.write(chunk)

  def flush(self) -> None:
    self._write_chunks(self.chunker.flush()) # type: ignore # flush is untyped.

  def close(self) -> None:
    self._write_chunks(self.chunker.finish()) # type: ignore # flush is untyped.
    self.file.close()

  @property
  def closed(self) -> bool:
    return self.file.closed

  @property
  def compression_ratio(self) -> float:
    return self.compressed_byte_count / self.input_byte_count


class ZstWriter(ZstWriterBase, BinaryIO):

  def __enter__(self) -> 'ZstWriter': return self

  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> None:
    self.close()

  def write(self, data:bytes) -> int:
    l = len(data)
    self.input_byte_count += l
    self._write_chunks(self.chunker.compress(data))
    return l


class ZstTextWriter(ZstWriterBase, TextIO):

  def __init__(self, file:BinaryIO, encoding:str=None, errors:str=None, level=6, threads=1, chunk_size=32768) -> None:
    self._encoding = encoding or 'utf-8'
    self._errors = errors or 'strict'
    super().__init__(file=file, level=level, threads=threads, chunk_size=chunk_size)

  def __enter__(self) -> 'ZstTextWriter': return self

  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> None:
    self.close()

  def write(self, text:str) -> int:
    data = text.encode(self.encoding)
    self.input_byte_count += len(data)
    self._write_chunks(self.chunker.compress(data))
    return len(text)

  @property
  def encoding(self) -> str:
    return self._encoding

  @property
  def errors(self) -> str:
    return self._errors
