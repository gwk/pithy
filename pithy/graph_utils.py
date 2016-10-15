# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re

from html import escape as html_escape
from sys import stdout


def visit_nodes(start_nodes, visitor):
  '''
  Starting with `start_nodes`, call `visitor` with each node.
  `visitor` should return discovered nodes to be visited.
  Each node is visited exactly once.
  The set of all visited nodes is returned.
  '''
  remaining = set(start_nodes)
  visited = set()
  while remaining:
    node = remaining.pop()
    visited.add(node)
    discovered = visitor(node)
    remaining.update(n for n in discovered if n not in visited)
  return visited


# graphviz dot utliities.


dot_bare_id_re = re.compile(r'[_a-zA-Z][_a-zA-Z0-9]*')
dot_keywords = frozenset({'node', 'edge', 'graph', 'digraph', 'subgraph', 'strict'})

def dot_id_quote(name):
  '''
  Properly quote an identifier.
  The DOT language has a facility for double-quoted strings, but the escape semantics are flawed,
  in that double backslash is not an escape sequence.
  Since XML escaping is also allowed, we just use that approach instead.
  '''
  if isinstance(name, (int, float)): return str(name)
  return name if dot_bare_id_re.fullmatch(name) and name not in dot_keywords else '<{}>'.format(html_escape(name))


def write_dot_digraph_adjacency_contents(f, adjacency):
  for src, dsts in adjacency:
    src_quoted = dot_id_quote(src)
    f.write('  {} -> {{'.format(src_quoted))
    for dst in sorted(dsts):
      f.write(' ')
      f.write(dot_id_quote(dst))
    f.write(' };\n')


def write_dot_digraph_adjacency(f, adjacency, label=None):
  if label is None:
    f.write('strict digraph {')
  else:
    label_quoted = dot_id_quote(label)
    f.write('strict digraph {} {{\n'.format(label_quoted))
    f.write('  label={};\n'.format(dot_id_quote(label)))
  write_dot_digraph_adjacency_contents(f, adjacency)
  f.write('}\n')


def out_dot_digraph_adjacency(adjacency, label=None):
  write_dot_digraph_adjacency(stdout, adjacency=adjacency, label=label)
