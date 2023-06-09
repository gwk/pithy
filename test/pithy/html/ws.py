#!/usr/bin/env python3

from pithy.html import Body, Html, HtmlNode
from pithy.io import outL
from pithy.string import clip_prefix, clip_suffix
from utest import utest

from typing import List, Tuple


ws_normalizations:List[Tuple[str|HtmlNode,str]] = [
  ( '',
    ''),
  ( ' Leading and trailing space. ',
    '<p>Leading and trailing space.</p>'),
  ( '<p>Paragraph 0.</p>',
    '<p>Paragraph 0.</p>'),

  ( Html(Body(_=['\n', 'Hi.', '\n', '\n', 'Bye.\n'])),
    'Hi.\nBye.'),

  ( '<section>top<section>sub 1.</section><section> sub 2.</section></section>',
'''\
<section>
top
<section>sub 1.</section>
<section>sub 2.</section>
</section>''')
]


for src, exp, in ws_normalizations:
  if isinstance(src, HtmlNode):
    html = src
  else:
    html = Html.parse(src)

  assert isinstance(html, Html), html
  html.clean()
  body = html.body
  res = body.render_children_str()
  if res != exp:
    outL(f'test failure: normalization of: {src!r}')
    outL('\n------\nexpected:\n', exp)
    outL('\n------\nactual:\n', res)
