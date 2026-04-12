# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.parse import Adjacency, Atom, Infix, Left, parse_skel, Parser, Precedence, Prefix, Right, Suffix
from pithy.py.lex import lexer
from utest import utest


left = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Left(Infix('plus')),
      Left(Infix('star')),
 )))


utest(('+', ('+', 'a', ('*', 'b', 'c')), 'd'), parse_skel, left, 'expr', 'a + b * c + d')

utest(('+', ('*', 'a', 'b'), ('*', ('*', 'c', 'd'), 'e')), parse_skel, left, 'expr', 'a * b + c * d * e')


right = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Infix('plus')),
      Right(Infix('star')),
 )))

utest(('+', 'a', ('+', ('*', 'b', 'c'), 'd')), parse_skel, right, 'expr', 'a + b * c + d')

utest(('+', ('*', 'a', 'b'), ('*', 'c', ('*', 'd', 'e'))), parse_skel, right, 'expr', 'a * b + c * d * e')


left_right = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Left(Infix('plus')),
      Right(Infix('star')),
 )))

utest(('+', ('+', 'a', 'b'), ('*', 'c', ('*', 'd', 'e'))), parse_skel, left_right, 'expr', 'a + b + c * d * e')

utest(('+', ('+', ('*', 'a', ('*', 'b', 'c')), 'd'), 'e'), parse_skel, left_right, 'expr', 'a * b * c + d + e')


right_left = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Infix('plus')),
      Left(Infix('star')),
  )))

utest(('+', 'a', ('+', 'b', ('*', ('*', 'c', 'd'), 'e'))), parse_skel, right_left, 'expr', 'a + b + c * d * e')

utest(('+', ('*', ('*', 'a', 'b'), 'c'), ('+', 'd', 'e')), parse_skel, right_left, 'expr', 'a * b * c + d + e')


left_adj_dot = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Left(Adjacency()),
      Left(Infix('dot')),
 )))

utest(((('.', 'a', 'b'), 'c'), 'd'), parse_skel, left_adj_dot, 'expr', 'a.b c d')
utest((('a', ('.', 'b', 'c')), 'd'), parse_skel, left_adj_dot, 'expr', 'a b.c d')


left_dot_adj = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Left(Infix('dot')),
      Left(Adjacency()),
 )))

utest(('.', 'a', (('b', 'c'), 'd')), parse_skel, left_dot_adj, 'expr', 'a . b c d')
utest(('.', (('a', 'b'), 'c'), 'd'), parse_skel, left_dot_adj, 'expr', 'a b c . d')


right_adj_dot = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Adjacency()),
      Right(Infix('dot')),
 )))

utest((('.', 'a', 'b'), ('c', 'd')), parse_skel, right_adj_dot, 'expr', 'a.b c d')
utest(('a', (('.', 'b', 'c'), 'd')), parse_skel, right_adj_dot, 'expr', 'a b.c d')


right_dot_adj = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Infix('dot')),
      Right(Adjacency()),
 )))

utest(('.', 'a', ('b', ('c', 'd'))), parse_skel, right_dot_adj, 'expr', 'a . b c d')
utest(('.', ('a', ('b', 'c')), 'd'), parse_skel, right_dot_adj, 'expr', 'a b c . d')


right_adj_qmark = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Adjacency()),
      Right(Suffix('qmark')),
 )))

utest(('a', (('?', 'b'), 'c')), parse_skel, right_adj_qmark, 'expr', 'a b? c')


qmark_right_adj = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Suffix('qmark')),
      Right(Adjacency()),
 )))

utest(((('?', ('a', 'b')), 'c')), parse_skel, qmark_right_adj, 'expr', 'a b ? c')


right_adj_dash = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Adjacency()),
      Right(Prefix('dash')),
 )))

utest(('a', (('-', 'b'), 'c')), parse_skel, right_adj_dash, 'expr', 'a -b c')


dash_right_adj = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name'),
    expr=Precedence(
      ('name',),
      Right(Prefix('dash')),
      Right(Adjacency()),
 )))

utest(('a', ('-', ('b', 'c'))), parse_skel, dash_right_adj, 'expr', 'a - b c')
