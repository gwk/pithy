# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from functools import singledispatch
from typing import Iterator, List, Union

from pithy.html import Body, Html, HtmlNode, Section


def render_wu(node:HtmlNode) -> Iterator[str]:
  yield 'writeup v0\n\n' # TODO: Bump to v1.
  yield from _render(node, section_depth=0, max_top_nl=0)


@singledispatch
def _render(node:Union[str,HtmlNode], section_depth:int, max_top_nl:int) -> Iterator[str]:
  raise NotImplementedError(node)


@_render.register
def _(node:str, section_depth:int, max_top_nl:int) -> Iterator[str]:
  yield fmt_wu_text(node)


@_render.register # type: ignore
def _(node:HtmlNode, section_depth:int, max_top_nl:int) -> Iterator[str]:

  attrs_str = fmt_wu_node_attrs(node)
  ch = node.ch
  head_end = ' ' if ch else '>'
  yield f'<{node.tag}:{attrs_str}{head_end}'
  if not node.ch: return

  child_newlines = len(node.ch) > 1
  if child_newlines: yield '\n'
  for child in node.ch:
    yield from _render(child, section_depth=section_depth, max_top_nl=max_top_nl)
    if child_newlines: yield '\n'
  yield '>'


@_render.register # type: ignore
def _(node:Html, section_depth:int, max_top_nl:int) -> Iterator[str]:
  for el in node:
    yield from _render(el, section_depth, max_top_nl=max_top_nl)


@_render.register # type: ignore
def _(node:Body, section_depth:int, max_top_nl:int) -> Iterator[str]:
  for el in node:
    yield from _render(el, section_depth, max_top_nl=max_top_nl)


@_render.register # type: ignore
def _(node:Section, section_depth:int, max_top_nl:int) -> Iterator[str]:
  nl_count_top = min(max_top_nl, max(1, 3 - section_depth))
  nl_top = '\n' * nl_count_top
  nl_between = '\n' * max(1, 2 - section_depth)
  hashes = '#' * (section_depth+1)
  heading = node.heading
  heading_text = (' ' + heading.text) if heading else ''
  yield f'{nl_top}{hashes}{heading_text}{nl_between}'
  for el in node:
    if el is heading: continue
    yield from _render(el, section_depth+1, max_top_nl=max_top_nl)

#@_render.register # type: ignore
#def _render(node:P, section_depth:int, preceding_newlines:int) -> Iterator[str]:
#  pass


def fmt_wu_node_attrs(node:HtmlNode) -> str:
  'Return a string that is either empty or with a leading space, containing all of the formatted items.'
  parts: List[str] = []
  for k, v in node.attrs.items():
    k = node.replaced_attrs.get(k, k)
    if v is None: v = 'none'
    parts.append(f' {fmt_wu_attr(k)}={fmt_wu_attr(str(v))}')
  return ''.join(parts) + ';' if parts else ''


def fmt_wu_attr(attr:str) -> str:
  if wu_bare_attr_re.fullmatch(attr): return attr
  quote = "'"
  if "'" in attr and '"' not in attr: quote = '"'
  r = [quote]
  for char in attr:
    if char == '\\': r.append('\\\\')
    elif char == quote: r.append('\\' + quote)
    elif 0x20 <= ord(char) <= 0x7E: r.append(char)
    elif char == '\0': r.append('\\0')
    elif char == '\t': r.append('\\t')
    elif char == '\n': r.append('\\n')
    elif char == '\r': r.append('\\r')
    else: r.append(f'\\{hex(ord(char))};')
  r.append(quote)
  return ''.join(r)


def fmt_wu_text(text:str) -> str:
  return text # TODO


wu_bare_attr_re = re.compile(r'[-./0-9:@A-Z_a-z]+')
