#!/usr/bin/env python3

from pithy.html import Body, Div, Head, Html, Script, Style
from pithy.svg import Script as svg_Script, Style as svg_Style, Svg

'''
Test that we can embed SVG in HTML and that the SVG elements are parsed as SvgNode and not HtmlNode.
'''

html = Html(_=[
  Head(_=[
    Style('svg { background: #eee; }'),
    Script('/* HTML Script */.')]),
  Body(_=[
    Div(_=[
      'HTML.',
      Svg(_=[
        svg_Style('svg { background: #ddd; }'),
        svg_Script('/* SVG Script */.')])])])])

html_str = html.render_str()
parsed = Html.parse(html_str)

head = parsed.head
assert isinstance(head.pick('style'), Style)
assert isinstance(head.pick('script'), Script)

svg = parsed.body.pick('div').pick('svg')
assert isinstance(svg, Svg)
assert isinstance(svg.pick('style'), svg_Style), type(svg.pick('style'))
assert isinstance(svg.pick('script'), svg_Script)
