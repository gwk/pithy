#!/usr/bin/env python3

from pithy.parse import Adjacency, Atom, Infix, Left, Parser, Precedence, Right, Suffix, atom_text
from pithy.py.lex import lexer
from tolkien import Source
from utest import utest


left = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name', transform=atom_text),
    expr=Precedence(
      ('name',),
      Left(Infix('plus')),
      Left(Infix('star')),
    )))

utest(('+', ('+', 'a', ('*', 'b', 'c')), 'd'), left.parse, 'expr', Source('', 'a + b * c + d'))
utest(('+', ('*', 'a', 'b'), ('*', ('*', 'c', 'd'), 'e')), left.parse, 'expr', Source('', 'a * b + c * d * e'))


right = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name', transform=atom_text),
    expr=Precedence(
      ('name',),
      Right(Infix('plus')),
      Right(Infix('star')),
    )))

utest(('+', 'a', ('+', ('*', 'b', 'c'), 'd')), right.parse, 'expr', Source('', 'a + b * c + d'))
utest(('+', ('*', 'a', 'b'), ('*', 'c', ('*', 'd', 'e'))), right.parse, 'expr', Source('', 'a * b + c * d * e'))


left_adj_dot = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name', transform=atom_text),
    expr=Precedence(
      ('name',),
      Left(Adjacency()),
      Left(Infix('dot')),
    )))

utest(((('.', 'a', 'b'), 'c'), 'd'), left_adj_dot.parse, 'expr', Source('', 'a.b c d'))
utest((('a', ('.', 'b', 'c')), 'd'), left_adj_dot.parse, 'expr', Source('', 'a b.c d'))


left_dot_adj = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name', transform=atom_text),
    expr=Precedence(
      ('name',),
      Left(Infix('dot')),
      Left(Adjacency()),
    )))

utest(('.', 'a', (('b', 'c'), 'd')), left_dot_adj.parse, 'expr', Source('', 'a . b c d'))
utest(('.', (('a', 'b'), 'c'), 'd'), left_dot_adj.parse, 'expr', Source('', 'a b c . d'))


right_adj_dot = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name', transform=atom_text),
    expr=Precedence(
      ('name',),
      Right(Adjacency()),
      Right(Infix('dot')),
    )))

utest((('.', 'a', 'b'), ('c', 'd')), right_adj_dot.parse, 'expr', Source('', 'a.b c d'))
utest(('a', (('.', 'b', 'c'), 'd')), right_adj_dot.parse, 'expr', Source('', 'a b.c d'))


right_dot_adj = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name', transform=atom_text),
    expr=Precedence(
      ('name',),
      Right(Infix('dot')),
      Right(Adjacency()),
    )))

utest(('.', 'a', ('b', ('c', 'd'))), right_dot_adj.parse, 'expr', Source('', 'a . b c d'))
utest(('.', ('a', ('b', 'c')), 'd'), right_dot_adj.parse, 'expr', Source('', 'a b c . d'))


right_adj_qmark = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name', transform=atom_text),
    expr=Precedence(
      ('name',),
      Right(Adjacency()),
      Right(Suffix('qmark')),
    )))

utest(('a', (('?', 'b'), 'c')), right_adj_qmark.parse, 'expr', Source('', 'a b? c'))


right_qmark_adj = Parser(lexer,
  drop=('spaces',),
  rules=dict(
    name=Atom('name', transform=atom_text),
    expr=Precedence(
      ('name',),
      Right(Suffix('qmark')),
      Right(Adjacency()),
    )))

utest(('?', ('a', 'b')), right_qmark_adj.parse, 'expr', Source('', 'a b ?'))
