# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Optional, Type
from types import TracebackType

Opt = Optional

# These types are helpful when defining `__exit__`:
# def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> bool: ...
OptTypeBaseExc = Optional[Type[BaseException]]
OptBaseExc = Optional[BaseException]
OptTraceback = Optional[TracebackType]
