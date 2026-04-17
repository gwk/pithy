# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.html import Body, Html, HtmlNode
from pithy.io import outL
from pithy.string import pluralize


ws_normalizations:list[tuple[str|HtmlNode,str]] = [
  ( '',
    ''),
  ( ' Leading and trailing space. ',
    'Leading and trailing space.'),
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

failures = 0

for src, exp, in ws_normalizations:
  if isinstance(src, HtmlNode):
    html = src
  else:
    html = Html.parse(src)

  assert isinstance(html, Html)
  html.clean()
  body = html.body
  res = body.render_children_str()
  if res != exp:
    outL(f'test failure: normalization of: {src!r}')
    outL('\n------\nexpected:\n', exp)
    outL('\n------\nactual:\n', res)
    failures += 1

if failures:
  outL(f'\n{failures} test {pluralize(failures, "failure")}.\n')
  exit(1)
