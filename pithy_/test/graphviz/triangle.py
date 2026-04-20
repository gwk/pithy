#!/usr/bin/env python3

from sys import stdout
from typing import cast, Mapping

from pithy.graphviz import GraphvizAdjacency, GraphvizName, GraphvizValues, write_dot_digraph_adjacency


write_dot_digraph_adjacency(stdout, [('a', 'b'), ('b', 'c'), ('c', 'a')], label='Plain')

write_dot_digraph_adjacency(stdout, cast(Mapping, {'a':['b'], 'b':['c'], 'c':['a']}), label='Plain (dict)')


graph:Mapping = {
  'a': ['b'],
  'b': [('c', dict(label='b->c'))],
  'c': ['a'],
}

write_dot_digraph_adjacency(stdout, graph, nodes={'a':dict(style='bold')}, label='Attributed')
