#!/usr/bin/env python3

from utest import utest, utest_call
from functools import singledispatch
from pithy.tree import *


@utest_call
def test_transform_tree_0():

  @singledispatch
  def get_children(node: Iterable) -> Iterable:
    try: return iter(node)
    except TypeError: return None

  @get_children.register
  def _(node:dict) -> Iterable: return node.values()

  @singledispatch
  def visit(node, stack, results):
    return (type(node).__name__, *results)

  @visit.register
  def _(node:int, stack, results):
    return ('int', node)

  input = {
    'a': 0,
    'b': [
      (1, 2)]}

  output = ('dict',
    ('int', 0),
    ('list',
      ('tuple',
        ('int', 1),
        ('int', 2))))

  utest(output, transform_tree, input, get_children, visit)


@utest_call
def test_transform_tree_1():

  def get_children(node: Iterable) -> Iterable:
    return None if isinstance(node, (int, str)) else node

  @singledispatch
  def visit(node: Iterable, stack, results):
    return results or node

  @visit.register
  def _(node:tuple, stack, results):
    yield from results # flatten tuples out.

  @visit.register
  def _(node:str, stack, results):
    raise OmitNode

  input = [
    'omitted',
    [0],
    [ (1, 2),
      (3, 4)]]

  output = [[0], [1, 2, 3, 4]]

  utest(output, transform_tree, input, get_children, visit)
