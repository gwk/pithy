# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.parse import Adjacency, Atom, Infix, Left, Parser, Precedence, Right, Suffix
from pithy.py.lex import lexer
from tolkien import Source
from utest import utest


left = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Left(Infix('plus')),
      Left(Infix('star')),
    ),
  ),
)

utest(('+', ('+', 'a', ('*', 'b', 'c')), 'd'), left.parse, 'expr', Source('', 'a + b * c + d'), skeletonize=True)

utest(('+', ('*', 'a', 'b'), ('*', ('*', 'c', 'd'), 'e')), left.parse, 'expr', Source('', 'a * b + c * d * e'),
  skeletonize=True)


right = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Infix('plus')),
      Right(Infix('star')),
    ),
  ),
)

utest(('+', 'a', ('+', ('*', 'b', 'c'), 'd')), right.parse, 'expr', Source('', 'a + b * c + d'), skeletonize=True)

utest(('+', ('*', 'a', 'b'), ('*', 'c', ('*', 'd', 'e'))), right.parse, 'expr', Source('', 'a * b + c * d * e'),
  skeletonize=True)


left_adj_dot = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Left(Adjacency()),
      Left(Infix('dot')),
    ),
  ),
)

utest(((('.', 'a', 'b'), 'c'), 'd'), left_adj_dot.parse, 'expr', Source('', 'a.b c d'), skeletonize=True)
utest((('a', ('.', 'b', 'c')), 'd'), left_adj_dot.parse, 'expr', Source('', 'a b.c d'), skeletonize=True)


left_dot_adj = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Left(Infix('dot')),
      Left(Adjacency()),
    ),
  ),
)

utest(('.', 'a', (('b', 'c'), 'd')), left_dot_adj.parse, 'expr', Source('', 'a . b c d'), skeletonize=True)
utest(('.', (('a', 'b'), 'c'), 'd'), left_dot_adj.parse, 'expr', Source('', 'a b c . d'), skeletonize=True)


right_adj_dot = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Adjacency()),
      Right(Infix('dot')),
    ),
  ),
)

utest((('.', 'a', 'b'), ('c', 'd')), right_adj_dot.parse, 'expr', Source('', 'a.b c d'), skeletonize=True)
utest(('a', (('.', 'b', 'c'), 'd')), right_adj_dot.parse, 'expr', Source('', 'a b.c d'), skeletonize=True)


right_dot_adj = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Infix('dot')),
      Right(Adjacency()),
    ),
  ),
)

utest(('.', 'a', ('b', ('c', 'd'))), right_dot_adj.parse, 'expr', Source('', 'a . b c d'), skeletonize=True)
utest(('.', ('a', ('b', 'c')), 'd'), right_dot_adj.parse, 'expr', Source('', 'a b c . d'), skeletonize=True)


right_adj_qmark = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Adjacency()),
      Right(Suffix('qmark')),
    ),
  ),
)

utest(('a', (('?', 'b'), 'c')), right_adj_qmark.parse, 'expr', Source('', 'a b? c'), skeletonize=True)


right_qmark_adj = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Suffix('qmark')),
      Right(Adjacency()),
    ),
  ),
)

utest(('?', ('a', 'b')), right_qmark_adj.parse, 'expr', Source('', 'a b ?'), skeletonize=True)
