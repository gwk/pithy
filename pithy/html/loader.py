# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, BinaryIO, Dict


def load_html(file:BinaryIO, encoding:str=None, **kwargs:Any) -> Any:
  from html5_parser import parse
  data = file.read()
  html = parse(data, transport_encoding=encoding, return_root=True, **kwargs)
  if 'treebuilder' in kwargs: return html

  # If none of the html5_parser `treebuilder` options was supplied,
  # then it will use the fast `lxml` option by default.
  # We then transform this tree into a generic dictionary tree.
  # Attributes are stored with string keys,
  # and node children and text are interleaved under increasing numeric keys.

  def transform(obj:Any) -> Any:
    res:Dict = {'': obj.tag}
    res.update(sorted(obj.items()))
    idx = 0
    t = obj.text
    if t:
      res[idx] = t
      idx += 1
    for child in obj:
      res[idx] = transform(child)
      idx += 1
      t = child.tail
      if t:
        res[idx] = t
        idx += 1
    return res

  return transform(html)
