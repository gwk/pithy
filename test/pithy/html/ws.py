#!/usr/bin/env python3

from utest import *
from pithy.io import *
from pithy.html import *
from pithy.string import clip_prefix, clip_suffix
from typing import *


ws_normalizations:List[Tuple[MuChild,MuChild]] = [
  ( '',
    ''),
  ( ' Leading and trailing space. ',
    'Leading and trailing space.'),
  ( '<p>Paragraph 0.</p>',
    '<p>Paragraph 0.</p>'),

  ( Body(ch=['\n', 'Hi.', '\n', '\n', 'Bye.\n']),
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

  html.clean()
  body = html.body if isinstance(html, Html) else html
  res = body.render_str()
  res = clip_prefix(res, '<body>')
  res = clip_suffix(res, '</body>\n')
  if res != exp:
    outL(f'test failure: normalization of: {src!r}')
    outL('expected:\n', exp)
    outL('\n------\nactual:\n', res)

