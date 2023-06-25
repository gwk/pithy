# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from types import GeneratorType
from typing import Callable, Generator, Iterable, Iterator, Optional, Protocol, TypeVar, Union

from .exceptions import OmitNode
from .iterable import iter_values


_C = TypeVar('_C')
_T = TypeVar('_T', contravariant=True)
_R = TypeVar('_R')

_Stack = tuple[_T, ...]
_VisitResult = Union[_R, Generator[_R, None, None]]

class _GetChildrenFn(Protocol[_C]):
  def __call__(self, node:_C) -> Optional[Iterable[_C]]: ...

class _TransformVisitor(Protocol[_T, _R]):
  def __call__(self, node:_T, stack:_Stack, transformed_children:list[_R]) -> _VisitResult: ...


def transform_tree(root:_T, get_children:_GetChildrenFn[_T], visit:_TransformVisitor[_T, _R]) -> _R:
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
  if isinstance(res, GeneratorType): raise ValueError(res)
  else: return res # type: ignore[return-value]


def _transform_tree(node:_T, get_children:_GetChildrenFn, visit:_TransformVisitor, stack:_Stack) -> _VisitResult:
  results: list[_R] = [] # type: ignore[valid-type]
  children = get_children(node)
  if children:
    child_stack = (*stack, node)
    for child in children:
      try: r = _transform_tree(child, get_children, visit, child_stack)
      except OmitNode: continue
      if isinstance(r, GeneratorType):
        results.extend(r)
      else:
        results.append(r)
  return visit(node, stack, results)


def visit_tree_preorder(obj:_T, get_values:Callable[[_T],Iterable[_T]]=iter_values) -> Iterator[_T]:
  yield obj
  for el in get_values(obj):
    yield from visit_tree_preorder(el, get_values)


def visit_tree_postorder(obj:_T, get_values:Callable[[_T],Iterator[_T]]=iter_values) -> Iterator[_T]:
  for el in get_values(obj):
    yield from visit_tree_postorder(el, get_values)
  yield obj
