# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Graphviz dot utliities.'

import re
from html import escape as html_escape
from sys import stdout
from typing import Any, Callable, Dict, Iterable, TextIO, Tuple, Union


Name = Union[int, float, str]

dot_bare_id_re = re.compile(r'[_a-zA-Z][_a-zA-Z0-9]*')
dot_keywords = frozenset({'node', 'edge', 'graph', 'digraph', 'subgraph', 'strict'})


def dot_id_quote(name: Name) -> str:
  '''
  Properly quote an identifier.
  The DOT language has a facility for double-quoted strings, but the escape semantics are flawed,
  in that double backslash is not an escape sequence.
  Since XML escaping is also allowed, we just use that approach instead.
  '''
  if isinstance(name, (int, float)): return str(name)
  return name if (dot_bare_id_re.fullmatch(name) and name not in dot_keywords) else f'<{html_escape(name)}>'


AdjacencyIterable = Iterable[Tuple[Name, Iterable[Name]]]

def write_dot_digraph_adjacency_contents(f: TextIO, adjacency: AdjacencyIterable) -> None:
  for src, dsts in adjacency:
    src_quoted = dot_id_quote(src)
    f.write(f'  {src_quoted} -> {{')
    for dst in sorted(dsts):
      f.write(' ')
      f.write(dot_id_quote(dst))
    f.write(' };\n')


def write_dot_digraph_adjacency(f: TextIO, adjacency: AdjacencyIterable, **kwargs) -> None:
  label = kwargs.get('label')
  if label is None:
    f.write('strict digraph {')
  else:
    f.write(f'strict digraph {dot_id_quote(label)} {{\n')
  for k, v in kwargs.items():
    validator = graph_prop_validators[k]
    if not validator(v): raise ValueError(f'value for {k} failed validation: {v!r}')
    f.write(f'  {k}={dot_id_quote(v)};\n')
  write_dot_digraph_adjacency_contents(f, adjacency)
  f.write('}\n')


def out_dot_digraph_adjacency(adjacency: AdjacencyIterable, **kwargs) -> None:
  write_dot_digraph_adjacency(stdout, adjacency=adjacency, **kwargs)


graph_prop_validators: Dict[str, Callable[[Any], bool]] = {
  'label': lambda v: isinstance(v, str),
  'rankdir': lambda v: (v in {'TB', 'BT', 'LR', 'RL'}),
}