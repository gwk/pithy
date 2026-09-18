# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from pithy.html import Div, Html, HtmlNode, P, Template
from pithy.html.loader import load_html
from pithy.loader import load, LoaderException
from pithy.svg import Svg
from utest import utest_exc, utest_run, utest_val, utest_val_type


source = '<div>before<!-- note -->between<p>inside</p>after</div>'


@utest_run
def _() -> None:
  'Preserve mixed content and leave caller-owned streams open.'
  for stream in (StringIO(source), BytesIO(source.encode())):
    html = HtmlNode.parse_file(stream, sanitize=False)
    utest_val_type(Html, html)
    div = html.body.pick(Div)
    utest_val(['before', HtmlNode(tag='!COMMENT', _=[' note ']), 'between', P('inside'), 'after'], div._)
    utest_val(False, stream.closed)


@utest_run
def _() -> None:
  'Require an explicit keyword-only sanitization choice at every HTML entry point.'
  utest_exc(TypeError, Html.parse, source)
  utest_exc(TypeError, Html.parse, source, False)
  utest_exc(TypeError, Html.parse_file, StringIO(source))
  utest_exc(TypeError, Html.parse_file, StringIO(source), False)
  utest_exc(TypeError, load_html, StringIO(source))
  dirty = '<p onclick="alert(1)">hello<script>alert(2)</script><a href="javascript:alert(3)">link</a></p>'
  clean = Html.parse(dirty, sanitize=True)
  raw = Html.parse(dirty, sanitize=False)
  utest_val(None, clean.find_opt('script'))
  utest_val(None, clean.find('p').get('onclick'))
  utest_val(None, clean.find('a').get('href'))
  utest_val('alert(2)', raw.find('script').text)
  utest_val('alert(1)', raw.find('p').get('onclick'))
  utest_val('javascript:alert(3)', raw.find('a').get('href'))
  with TemporaryDirectory() as directory:
    path = Path(directory) / 'sample.html'
    path.write_text(dirty)
    for file in (path, str(path), bytes(path)):
      utest_val(clean, Html.parse_file(file, sanitize=True))
      utest_val(raw, Html.parse_file(file, sanitize=False))
    utest_val(clean, load_html(str(path), sanitize=True))
    utest_val(raw, load(str(path), sanitize=False))
    utest_exc(LoaderException, load, str(path))


@utest_run
def _() -> None:
  'Use HTML5 tree construction, including implied end tags and template contents.'
  html = Html.parse('<p>one<p>two<template><div>content</div></template>', sanitize=False)
  utest_val(['one\n\n', 'twocontent\n\n'], [p.text for p in html.body.pick_all(P)])
  utest_val('content', html.find(Template).pick(Div).text)
  utest_val('', Html.parse('', sanitize=False).body.text)
  utest_val('caf\u00e9\n\n', Html.parse(b'<p>caf\xe9</p>', sanitize=False, encoding='windows-1252').body.text)
  utest_val('caf\u00e9\n\n', Html.parse(b'<meta charset="utf-8"><p>caf\xc3\xa9</p>', sanitize=False).body.text)
  svg = Html.parse('<svg viewBox="0 0 1 1"><foreignObject><div>HTML</div></foreignObject></svg>',
    sanitize=False).body.pick(Svg)
  utest_val('0 0 1 1', svg.get('viewBox'))
  utest_val_type(Div, svg.pick('foreignObject').pick('div'))
