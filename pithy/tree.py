# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Callable, Generator, Iterable, Iterator, List, Optional, Tuple, TypeVar, Union


_T = TypeVar('_T')
_R = TypeVar('_R')

_Stack = Tuple[_T, ...]
_VisitResult = Union[_R, Generator[_R, None, None]]
_GetChildrenFn = Callable[[_T], Optional[Iterable[_T]]]
_VisitFn = Callable[[_T, _Stack, List[_R]], _VisitResult]

# We check if the returned value from the visit function is that of a generator.
# In order to do so, we must create one and get its runtime type.
def _g() -> Iterator[None]: yield None
_Generator = type(_g())


class OmitNode(Exception): pass


def transform_tree(root:_T, get_children:_GetChildrenFn, visit:_VisitFn) -> _VisitResult:
  '''
  The `visit` function takes these parameters:
  * node: the current node.
  * stack: the stack of parent nodes.
  * results: the transformed children.
  `visit` should return either a single result node or else a generator of results; in the latter case the results are flattened with those of the node's siblings.
  '''
  return _transform_tree(root, get_children, visit, ())


def _transform_tree(node:_T, get_children:_GetChildrenFn, visit:_VisitFn, stack:_Stack) -> _VisitResult:
  results: List[_R] = [] # type: ignore
  children = get_children(node)
  if children:
    child_stack = (*stack, node)
    for child in children:
      try: r = _transform_tree(child, get_children, visit, stack)
      except OmitNode: continue
      if isinstance(r, _Generator):
        results.extend(r)
      else:
        results.append(r)
  return visit(node, stack, results)
