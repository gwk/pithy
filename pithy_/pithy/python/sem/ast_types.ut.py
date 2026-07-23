# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# pyright: reportDeprecated=false

import ast
from ast import (AST, AugLoad, AugStore, boolop, cmpop, Del, excepthandler, expr, expr_context, ExtSlice, Index, Load, mod,
  operator, Param, pattern, slice, stmt, Store, Suite, type_ignore, type_param, unaryop)
from inspect import get_annotations, getmembers, isclass
from typing import Any, get_args, get_origin, Union

from pithy.python.sem import ast_field_types, ast_to_sem_types, SemRef
from pithy.type_utils import nonopt_union


deprecated_types = frozenset((AugLoad, AugStore, Suite, Index, ExtSlice, Param))
ctx_types = frozenset((Del, Load, Store))
parent_ast_types = frozenset((boolop, cmpop, excepthandler, expr, expr_context, mod, operator, pattern, slice, stmt, type_ignore, type_param, unaryop))
ignored_types = deprecated_types | ctx_types | parent_ast_types


def sem_type_for_ast_type(ast_type:type) -> Any:
  origin = get_origin(ast_type)
  if origin is None:
    if issubclass(ast_type, AST):
      return ast_to_sem_types[ast_type]
    if ast_type in (int, str, object):
      return ast_type
  if origin is Union:
    nonopt = nonopt_union(ast_type)
    assert get_origin(nonopt) is not Union
    return Union[(sem_type_for_ast_type(nonopt), None)]
  if origin is list:
    el_type = get_args(ast_type)[0]
    return list[sem_type_for_ast_type(el_type)] # type: ignore[misc]
  raise NotImplementedError(ast_type)


def get_ast_subclasses() -> list[type[AST]]:
  #return sorted([t for _, t in getmembers(ast, isclass) if issubclass(t, AST) and t is not AST], key=lambda t: t.__name__)
  return [t for _, t in getmembers(ast, isclass) if issubclass(t, AST) and t is not AST]


_observed_ast_field_types:set[type] = set()

for ast_type in get_ast_subclasses():
  if ast_type in ignored_types: continue

  _observed_ast_field_types.update(ast_type._field_types.values())

  sem_type = ast_to_sem_types[ast_type]

  ast_types = ast_type._field_types
  sem_types = get_annotations(sem_type)
  del sem_types[sem_type.ast_key]

  if 'ctx' in ast_types:
    assert issubclass(sem_type, SemRef)
    del ast_types['ctx']

  ast_names = set(ast_types.keys())
  sem_names = set(sem_types.keys())

  assert ast_names == sem_names
  for name in ast_names:
    ast_field_type = ast_types[name]
    sem_field_type = sem_types[name]
    exp_field_type = sem_type_for_ast_type(ast_field_type)
    assert sem_field_type == exp_field_type, (sem_type, name, sem_field_type, exp_field_type, ast_field_type)


if ast_field_types != _observed_ast_field_types:
  print(f'ast_field_types != _observed_ast_field_types:\n  expected: {ast_field_types}\n  actual: {_observed_ast_field_types}')
