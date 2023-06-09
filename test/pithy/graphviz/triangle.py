#!/usr/bin/env python3

from sys import stdout

from pithy.graphviz import write_dot_digraph_adjacency


write_dot_digraph_adjacency(stdout, ['ab', 'bc', 'ca'], label='Plain')

write_dot_digraph_adjacency(stdout, dict(['ab', 'bc', 'ca']), label='Plain (dict)')

graph = {
  'a': 'b',
  'b': [('c', dict(label='b->c'))],
  'c': 'a',
}

write_dot_digraph_adjacency(stdout, graph, nodes={'a':dict(style='bold')}, label='Attributed')
