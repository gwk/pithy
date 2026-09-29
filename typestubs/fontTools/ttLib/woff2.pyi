# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from os import PathLike
from typing import BinaryIO


def compress(input_file:str|PathLike[str]|BinaryIO, output_file:str|PathLike[str]|BinaryIO, transform_tables:set[str]|None=None
 ) -> None: ...
