from zstandard import ZstdCompressor # type: ignore
from typing import BinaryIO, Iterable, TextIO


class ZstWriterBase:

  def __init__(self, file:BinaryIO, level=6, threads=1, chunk_size=32768) -> None:
    self.file = file
    self.compressor = ZstdCompressor(level=level, threads=1)
    self.chunker = self.compressor.chunker(chunk_size=chunk_size)
    self.input_byte_count = 0
    self.compressed_byte_count = 0

  def _write_chunks(self, chunks:Iterable[bytes]) -> None:
    for chunk in chunks:
      self.compressed_byte_count += self.file.write(chunk)

  def flush(self) -> None:
    self._write_chunks(self.chunker.flush())

  def close(self) -> None:
    self._write_chunks(self.chunker.finish())
    self.file.close()

  @property
  def closed(self) -> bool:
    return self.file.closed

  @property
  def compression_ratio(self) -> float:
    return self.compressed_byte_count / self.input_byte_count


class ZstWriter(ZstWriterBase, BinaryIO):

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
