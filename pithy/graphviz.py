# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Graphviz dot utliities.'

import re
from html import escape as html_escape
from sys import stdout
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, TextIO, Tuple, Union


GraphvizName = Union[int, float, str]

GraphvizAttrs = Mapping[str,GraphvizName]
GraphvizValAttrs = Tuple[GraphvizName,GraphvizAttrs]
GraphvizValues = Union[Iterable[GraphvizName], Iterable[GraphvizValAttrs], Mapping[GraphvizName,GraphvizAttrs]]
GraphvizAdjacency = Union[Mapping[GraphvizName,GraphvizValues], Iterable[Tuple[GraphvizName,GraphvizValues]]]
GraphvizNodes = Mapping[GraphvizName,GraphvizAttrs]

dot_bare_id_re = re.compile(r'[_a-zA-Z][_a-zA-Z0-9]*')
dot_quotable_id_re = re.compile(r'([ !#-\[\]-~\w]| )+') # Exclude double-quote and backslash; allow non-ascii word chars.
dot_keywords = frozenset({'node', 'edge', 'graph', 'digraph', 'subgraph', 'strict'})


def dot_id_quote(name:GraphvizName) -> str:
  '''
  Properly quote an identifier.
  The DOT language has two quotation mechanisms:
  * backslash double-quote escape, which is flawed because double backslash is not also an escape;
  * HTML escapes surrounded by angle brackets.
  we use the double-quote syntax when no escaping is required because it looks nicer,
  but rely on HTML escaping for everything else.
  See https://www.graphviz.org/doc/info/lang.html.
  '''
  if isinstance(name, (int, float)): return str(name)
  assert isinstance(name, str), name
  if dot_bare_id_re.fullmatch(name) and name not in dot_keywords: return name
  if dot_quotable_id_re.fullmatch(name): return f'"{name}"'
  return f'<{html_escape(name)}>'


def write_dot_digraph_adjacency_contents(f: TextIO, adjacency:GraphvizAdjacency) -> None:
  if isinstance(adjacency, dict): adjacency = adjacency.items()
  for src, dsts in adjacency: # type: ignore
    if isinstance(dsts, dict): dsts = dsts.items()
    src_quoted = dot_id_quote(src)
    for dst in dsts:
      attrs_str = ''
      if isinstance(dst, tuple):
        dst, attrs = dst
        if not isinstance(attrs, dict): raise ValueError(attrs)
        attrs_str = fmt_dot_attrs(attrs)
      f.write(f'{src_quoted} -> {dot_id_quote(dst)}{attrs_str};\n')


def write_dot_digraph_adjacency(f: TextIO, adjacency:GraphvizAdjacency, nodes:GraphvizNodes=None, **kwargs) -> None:
  label = dot_id_quote(kwargs.get('label', ''))
  if label: label += ' '
  f.write(f'strict digraph {label}{{\n')
  # Graph attributes.
  for k, v in kwargs.items():
    validator = graph_prop_validators[k]
    if not validator(v): raise ValueError(f'value for {k} failed validation: {v!r}')
    f.write(f'{k}={dot_id_quote(v)};\n')
  # Nodes.
  if nodes:
    for node, attrs in nodes.items():
      f.write(f'{dot_id_quote(node)}{fmt_dot_attrs(attrs)};\n')
  # Edges.
  write_dot_digraph_adjacency_contents(f, adjacency)
  f.write('}\n')


def fmt_dot_attrs(attrs:Optional[GraphvizAttrs]) -> str:
  if not attrs: return ''
  s = ', '.join(f'{k}={dot_id_quote(v)}' for k, v in attrs.items())
  return f' [{s}]'

def out_dot_digraph_adjacency(adjacency:GraphvizAdjacency, **kwargs) -> None:
  write_dot_digraph_adjacency(stdout, adjacency=adjacency, **kwargs)


graph_prop_validators: Dict[str, Callable[[Any], bool]] = {
  'label': lambda v: isinstance(v, str),
  'rankdir': lambda v: (v in {'TB', 'BT', 'LR', 'RL'}),
}
