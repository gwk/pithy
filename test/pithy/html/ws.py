#!/usr/bin/env python3

from utest import *
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

  #( Body(ch=['\n', 'Hi.', '\n', '\n', 'bye.']),
  #  ''),
]


for src, norm, in ws_normalizations:
  if isinstance(src, HtmlNode):
    html = src
  else:
    html = Html.parse(src)

  html.clean()
  body = html.body if isinstance(html, Html) else html
  res = body.render_str()
  res = clip_prefix(res, '<body>')
  res = clip_suffix(res, '</body>\n')
  utest_val(norm, res, f'normalization of: {src!r}')

