# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.html import Body, Div, Head, Html, Script, Style
from pithy.svg import Script as svg_Script, Style as svg_Style, Svg
from utest import utest_type, utest_val_type


'''
Test that we can embed SVG in HTML and that the SVG elements are parsed as SvgNode and not HtmlNode.
'''

html = Html(_=[
  Head(_=[
    Style('svg { background: #eee; }'),
    Script('/* HTML Script. */')]),
  Body(_=[
    Div(_=[
      'HTML.',
      Svg(_=[
        svg_Style('svg { background: #ddd; }'),
        svg_Script('/* SVG Script. */')])])])])

html_str = html.render_str()
parsed = Html.parse(html_str)

head = parsed.head
utest_type(Style, head.pick, 'style')
utest_type(Script, head.pick, 'script')

svg = parsed.body.pick('div').pick('svg')
utest_val_type(Svg, svg)
utest_type(svg_Style, svg.pick, 'style')
utest_type(svg_Script, svg.pick, 'script')
