# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Iterator


# We check if the returned value from the visit function is that of a generator.
# In order to do so, we must create one and get its runtime type.
def _g() -> Iterator[None]: yield None
GeneratorType = type(_g())
