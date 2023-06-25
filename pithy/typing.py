# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from types import TracebackType
from typing import Optional, Type


Opt = Optional

# These types are helpful when defining `__exit__`:
# def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> bool: ...
OptTypeBaseExc = Type[BaseException]|None
OptBaseExc = BaseException|None
OptTraceback = TracebackType|None
