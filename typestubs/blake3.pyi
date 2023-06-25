
from array import array
from ctypes import _CData
from mmap import mmap
from typing import Any, TypeVar, Union


ReadableBuffer = Union[bytes, bytearray, memoryview, array[Any], mmap, _CData]
#^ Derived from typeshed/stdlib/typeshed/__init__.py.

_Self = TypeVar("_Self")


class blake3:

  def __init__(self, data:ReadableBuffer=..., key:ReadableBuffer|None=None,
    derive_key_context:str|None=None, multithreading:bool=False) -> None: ...

  @property
  def block_size(self) -> int: ...

  @property
  def digest_size(self) -> int: ...

  @property
  def key_size(self) -> int: ...

  @property
  def name(self) -> str: ...

  def copy(self: _Self) -> _Self: ...

  def digest(self) -> bytes: ...

  def hexdigest(self) -> str: ...

  def update(self, __data: ReadableBuffer, *, multithreading=False) -> None: ...
