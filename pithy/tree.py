# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from functools import singledispatch
from typing import Any, Callable, Generator, Iterable, Iterator, List, Optional, Tuple, TypeVar, Union

from .generator import GeneratorType as _Generator


_T = TypeVar('_T')
_R = TypeVar('_R')

_Stack = Tuple[_T, ...]
_VisitResult = Union[_R, Generator[_R, None, None]]
_GetChildrenFn = Callable[[_T], Optional[Iterable[_T]]]
_VisitFn = Callable[[_T, _Stack, List[_R]], _VisitResult]


class OmitNode(Exception): pass


def transform_tree(root:_T, get_children:_GetChildrenFn, visit:_VisitFn) -> _R:
  '''
  `transform_tree` visits nodes, leaves-first, with the `visit` function,
  thereby generating a transformed tree.
  The `visit` function takes three parameters:
  * node: the current node.
  * stack: the stack of parent nodes.
  * results: the transformed children.

  `visit` should either:
  * return a single result node;
  * return a generator of results, which are flattened with those of the node's siblings;
  * raise OmitNode.
  '''
  res = _transform_tree(root, get_children, visit, ())
  if isinstance(res, _Generator): raise ValueError(res)
  else: return res # type: ignore


def _transform_tree(node:_T, get_children:_GetChildrenFn, visit:_VisitFn, stack:_Stack) -> _VisitResult:
  results: List[_R] = [] # type: ignore
  children = get_children(node)
  if children:
    child_stack = (*stack, node)
    for child in children:
      try: r = _transform_tree(child, get_children, visit, child_stack)
      except OmitNode: continue
      if isinstance(r, _Generator):
        results.extend(r)
      else:
        results.append(r)
  return visit(node, stack, results)


known_leaf_types = (bool, bytearray, bytes, complex, float, int, str, type(None), type(Ellipsis))


@singledispatch
def traverse_values(obj:Any) -> Iterator[Any]:
  if isinstance(obj, known_leaf_types): return

  if hasattr(obj, 'values'): # Treat as a mapping.
    yield from obj.values()

  try: it = iter(obj)
  except TypeError: return
  yield from it
