# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, BinaryIO, cast, TextIO, Union

from ..loader import FileOrPath
from . import HtmlNode


def load_html(file_or_path:FileOrPath, encoding:str='utf8', **kwargs:Any) -> Any:
  return HtmlNode.parse_file(cast(Union[str,TextIO,BinaryIO], file_or_path), encoding=encoding, **kwargs)
