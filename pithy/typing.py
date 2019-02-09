# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import *
from types import TracebackType

Opt = Optional

# For defining __exit__.
OptTypeBaseExc = Optional[Type[BaseException]]
OptBaseExc = Optional[BaseException]
OptTraceback = Optional[TracebackType]
