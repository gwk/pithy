# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import Namespace
from typing import Dict, List, Tuple

from pithy.graphviz import GraphvizAttrs, GraphvizName, GraphvizNodes, write_dot_digraph_adjacency

from .dfa import DFA


def output_dot(path_stem:str, dfas:List[DFA], pattern_descs:Dict[str,str], license:str, args:Namespace):

  for dfa in dfas:
    path = f'{path_stem}-{dfa.name}.dot'

    adjacency:Dict[GraphvizName,List[Tuple[GraphvizName,GraphvizAttrs]]] = {}
    for src, pairs in dfa.transition_descs():
      adjacency[src] = [(dst, dict(label=f'[{ranges_desc}]')) for dst, ranges_desc in pairs]

    nodes:GraphvizNodes = {
      node : dict(label=f'{node}: '+','.join(kind_set)) for node, kind_set in dfa.match_node_kind_sets.items() }

    with open(path, 'w') as f:
      write_dot_digraph_adjacency(f, adjacency, nodes=nodes, label=dfa.name)
