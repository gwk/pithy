# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from argparse import ArgumentParser
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from pithy.desc import outD
from pithy.iterable import iter_values
from pithy.lex import Lexer
from pithy.loader import load
from pithy.parse import Adjacency, Atom, Choice, choice_val, Left, Parser, Precedence, Struct
from tolkien import Source, Token


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
    exit('interactive mode requires a path argument.')

  roots = [load(p) for p in args.paths]


  if args.interactive:
    interactive_loop(args.query, roots)
  else:
    query = parse_query(' '.join(args.query))
    for result in query.run(roots):
      outD(result)


# Evaluation.

def interactive_loop(query_src:str, roots:list[Any]) -> None:
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
    return self.right.run(child for result in self.left.run(stream) for child in iter_values(result))


@dataclass
class FilterQuery(Query):
  predicate:Predicate

  def run(self, stream:Iterable[Any]) -> Iterable[Any]:
    p:Predicate = self.predicate
    for el in stream:
      if p(el):
        yield el


@dataclass
class SearchQuery(Query):
  predicate:Predicate

  def run(self, stream:Iterable[Any]) -> Iterable[Any]:
    p:Predicate = self.predicate
    for el in stream:
      if p(el):
        yield el
      else:
        yield from self.run(iter_values(el))


# Parsing.


def parse_query(src:str) -> Query:
  if not src or src.isspace(): return PassQuery()
  query = parser.parse_or_fail('oq', Source('query', src))
  assert isinstance(query, Query), query
  return query

def mk_type_pred(source:Source, token:Token) -> Predicate:
  type_name = source[token]
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

parser = Parser(lexer,
  drop=('line', 'space'),
  rules=dict(
    query=Precedence(
      ('filter', 'search'),
      Left(
        Adjacency(transform=lambda s, t, l, r: ChildQuery(l, r))
      ),
    ),
    search=Choice('pred', transform=lambda s, slc, name, predicate: SearchQuery(predicate)),
    filter=Struct('dot', 'pred', transform=lambda s, slc, f: FilterQuery(f[1])),

    pred=Choice('type_pred', transform=choice_val),

    type_pred=Atom('name', transform=mk_type_pred),
  ),
)
