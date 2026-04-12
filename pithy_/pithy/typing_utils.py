# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Buffer
from types import TracebackType
from typing import Protocol, Sized


# These types are helpful when defining `__exit__`:
# def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> bool: ...
OptTypeBaseExc = type[BaseException]|None
OptBaseExc = BaseException|None
OptTraceback = TracebackType|None


class SizedBuffer(Sized, Buffer, Protocol): ...
