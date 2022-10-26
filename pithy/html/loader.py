# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from html5_parser import parse

from ..html import HtmlNode
from ..loader import FileOrPath, binary_file_for


def load_html(file_or_path:FileOrPath, encoding:str|None=None, **kwargs:Any) -> Any:
  with binary_file_for(file_or_path) as file:
    data = file.read()
  html = parse(data, transport_encoding=encoding, return_root=True, **kwargs)
  if 'treebuilder' in kwargs: return html

  # If none of the html5_parser `treebuilder` options was supplied,
  # then it will use the fast `lxml` option by default.
  # Transform the resulting etree into a generic dictionary tree.
  return HtmlNode.from_etree(html)
