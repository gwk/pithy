# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from functools import singledispatch
from typing import Any, Callable, List, Match, Optional, Union

from ..buffer import Buffer
from ..desc import errD, outD
from ..fs import file_size, path_exists, remove_path
from ..io import *
from ..lex import Lexer, Token
from ..loader import load
from ..parse import Adjacency, Atom, Choice, Infix, Left, ParseError, Parser, Precedence, Prefix, Right, Rule, RuleName, Suffix
from ..tree import traverse_generic_tree


def main() -> None:
  '''
  # Syntax:

  ## Predicates
  * `NAME`: a type name.

  ## Filters
  * `*PREDICATE`: search the input object and its children using the specified predicate.
  * `>PREDICATE`: filter the input object using the specified predicate.
  '''

  parser = ArgumentParser(description='Object Query tool.')
  parser.add_argument('paths', nargs='+', help='Path to query.')
  parser.add_argument('-query', nargs='*', default=[], help='Query string.')
  parser.add_argument('-interactive', action='store_true', help='interactive mode.')
  args = parser.parse_args()

  if not args.paths and args.interactive:
    exit(f'interactive mode requires a path argument.')

  roots = [load(p) for p in args.paths]


  if args.interactive:
    interactive_loop(args.query, roots)
  else:
    query = parse_query(' '.join(args.query))
    for result in query.run(roots):
      outD(result)


# Evaluation.

def interactive_loop(query_src:str, roots:List[Any]) -> None:
  exit("INTERACTIVE LOOP NOT YET IMPLEMENTED.")


# Query language.

Predicate = Callable[[Any],bool]


class Query:
  def run(self, stream:Iterable[Any]) -> Iterable[Any]:
    raise NotImplementedError


class PassQuery(Query):
  def run(self, stream:Iterable[Any]) -> Iterable[Any]:
    return stream


@dataclass
class BinaryQuery(Query):
  left:Query
  right:Query


class ChainQuery(BinaryQuery):
  def run(self, stream:Iterable[Any]) -> Iterable[Any]:
    return self.right.run(self.left.run(stream))


class ChildQuery(BinaryQuery):
  def run(self, stream:Iterable[Any]) -> Iterable[Any]:
    return self.right.run(child for result in self.left.run(stream) for child in traverse_generic_tree(result))


@dataclass
class FilterQuery(Query):
  predicate:Predicate

  def run(self, stream:Iterable[Any]) -> Iterable[Any]:
    p:Predicate = self.predicate # type: ignore # long-standing mypy bug.
    for el in stream:
      if p(el):
        yield el


@dataclass
class SearchQuery(Query):
  predicate:Predicate

  def run(self, stream:Iterable[Any]) -> Iterable[Any]:
    p:Predicate = self.predicate # type: ignore # long-standing mypy bug.
    for el in stream:
      if p(el):
        yield el
      else:
        yield from self.run(traverse_generic_tree(el))


# Parsing.


def parse_query(src:str) -> Query:
  if not src or src.isspace(): return PassQuery()
  query = parser.parse_or_fail('oq', 'query', src)
  assert isinstance(query, Query), query
  return query

def mk_type_pred(token:Token) -> Predicate:
  type_name = token[0]
  def type_pred(obj:Any) -> bool:
    return type(obj).__name__ == type_name or (isinstance(obj, dict) and obj.get('') == type_name)
  return type_pred



# Lexer.

lexer = Lexer(flags='x', patterns=dict(
  line=r'\n',
  space=r'\s+',
  name=r'[-\w]+',
  par_o=r'\(',
  par_c=r'\)',
  sqb_o=r'\[',
  sqb_c=r'\]',
  cub_o=r'\{',
  cub_c=r'\}',
  star=r'\*',
  dot=r'\.',
  pipe=r'\|',
))

parser = Parser(lexer, dict(
  query=Precedence(
    ('filter', 'search'),
    Left(
      Adjacency(transform=lambda token, left, right: ChildQuery(left, right))
    ),
  ),
  search=Choice('pred', transform=lambda name, predicate: SearchQuery(predicate)),
  filter=Prefix('dot', 'pred', transform=lambda token, predicate: FilterQuery(predicate)),

  pred=Choice('type_pred', transform=lambda name, pred: pred),

  type_pred=Atom('name', mk_type_pred),
  ),
  drop=('line', 'space'))
