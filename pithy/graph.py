# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, Hashable, Iterable, Set, TypeVar


_H = TypeVar('_H', bound=Hashable)

def visit_nodes(start_nodes: Iterable[_H], visitor: Callable[[_H], Iterable[_H]]) -> Set[_H]:
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
