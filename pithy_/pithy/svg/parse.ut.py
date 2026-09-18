# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree.ElementTree import ParseError

from pithy.svg import Rect, Svg, SvgNode
from pithy.svg.loader import load_svg
from utest import utest, utest_exc, utest_run, utest_val, utest_val_type


source = '<svg viewBox="0 0 10 10">before<!-- note -->between<rect width="10"/>after</svg>'


@utest_run
def _() -> None:
  'Preserve SVG types, attributes, comments and mixed content from text and binary streams.'
  for stream in (StringIO(source), BytesIO(source.encode())):
    svg = SvgNode.parse_file(stream)
    utest_val_type(Svg, svg)
    utest_val({'viewBox': '0 0 10 10'}, svg.attrs)
    utest_val(['before', SvgNode(tag='!COMMENT', _=[' note ']), 'between', Rect(width='10'), 'after'], svg._)


@utest_run
def _() -> None:
  'Accept file paths and preserve namespace-qualified element and attribute names.'
  with TemporaryDirectory() as dir:
    path = Path(dir) / 'sample.svg'
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
      '<use xlink:href="#shape"/></svg>')
    for file in (path, str(path), bytes(path)):
      svg = SvgNode.parse_file(file)
      utest_val('{http://www.w3.org/2000/svg}svg', svg.tag)
      use = svg.pick('{http://www.w3.org/2000/svg}use')
      utest_val({'{http://www.w3.org/1999/xlink}href': '#shape'}, use.attrs)
    utest(svg, load_svg, path)


encoded = b'<?xml version="1.0" encoding="ISO-8859-1"?><svg><title>caf\xe9</title></svg>'
utest_val('caf\u00e9', SvgNode.parse_file(BytesIO(encoded)).title)
for invalid in ('', ' ', '<svg>', '<svg>&undefined;</svg>'):
  utest_exc(ParseError, SvgNode.parse_file, StringIO(invalid))
