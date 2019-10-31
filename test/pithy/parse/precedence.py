#!/usr/bin/env python3

from pithy.parse import Adjacency, Atom, Infix, Left, Parser, Precedence, Right, Suffix, token_extract_text
from pithy.py.lex import lexer
from tolkien import Source
from utest import *


left = Parser(lexer, dict(
    name=Atom('name', transform=token_extract_text),
    expr=Precedence(
      ('name',),
      Left(Infix('plus')),
      Left(Infix('star')),
    )),
  drop=('spaces',))

utest(('+', ('+', 'a', ('*', 'b', 'c')), 'd'), left.parse, 'expr', Source('', 'a + b * c + d'))
utest(('+', ('*', 'a', 'b'), ('*', ('*', 'c', 'd'), 'e')), left.parse, 'expr', Source('', 'a * b + c * d * e'))


right = Parser(lexer, dict(
    name=Atom('name', transform=token_extract_text),
    expr=Precedence(
      ('name',),
      Right(Infix('plus')),
      Right(Infix('star')),
    )),
  drop=('spaces',))

utest(('+', 'a', ('+', ('*', 'b', 'c'), 'd')), right.parse, 'expr', Source('', 'a + b * c + d'))
utest(('+', ('*', 'a', 'b'), ('*', 'c', ('*', 'd', 'e'))), right.parse, 'expr', Source('', 'a * b + c * d * e'))


left_adj_dot = Parser(lexer, dict(
    name=Atom('name', transform=token_extract_text),
    expr=Precedence(
      ('name',),
      Left(Adjacency()),
      Left(Infix('dot')),
    )),
  drop=('spaces',))

utest(((('.', 'a', 'b'), 'c'), 'd'), left_adj_dot.parse, 'expr', Source('', 'a.b c d'))
utest((('a', ('.', 'b', 'c')), 'd'), left_adj_dot.parse, 'expr', Source('', 'a b.c d'))


left_dot_adj = Parser(lexer, dict(
    name=Atom('name', transform=token_extract_text),
    expr=Precedence(
      ('name',),
      Left(Infix('dot')),
      Left(Adjacency()),
    )),
  drop=('spaces',))

utest(('.', 'a', (('b', 'c'), 'd')), left_dot_adj.parse, 'expr', Source('', 'a . b c d'))
utest(('.', (('a', 'b'), 'c'), 'd'), left_dot_adj.parse, 'expr', Source('', 'a b c . d'))


right_adj_dot = Parser(lexer, dict(
    name=Atom('name', transform=token_extract_text),
    expr=Precedence(
      ('name',),
      Right(Adjacency()),
      Right(Infix('dot')),
    )),
  drop=('spaces',))

utest((('.', 'a', 'b'), ('c', 'd')), right_adj_dot.parse, 'expr', Source('', 'a.b c d'))
utest(('a', (('.', 'b', 'c'), 'd')), right_adj_dot.parse, 'expr', Source('', 'a b.c d'))


right_dot_adj = Parser(lexer, dict(
    name=Atom('name', transform=token_extract_text),
    expr=Precedence(
      ('name',),
      Right(Infix('dot')),
      Right(Adjacency()),
    )),
  drop=('spaces',))

utest(('.', 'a', ('b', ('c', 'd'))), right_dot_adj.parse, 'expr', Source('', 'a . b c d'))
utest(('.', ('a', ('b', 'c')), 'd'), right_dot_adj.parse, 'expr', Source('', 'a b c . d'))


right_adj_qmark = Parser(lexer, dict(
    name=Atom('name', transform=token_extract_text),
    expr=Precedence(
      ('name',),
      Right(Adjacency()),
      Right(Suffix('qmark')),
    )),
  drop=('spaces',))

utest(('a', (('?', 'b'), 'c')), right_adj_qmark.parse, 'expr', Source('', 'a b? c'))


right_qmark_adj = Parser(lexer, dict(
    name=Atom('name', transform=token_extract_text),
    expr=Precedence(
      ('name',),
      Right(Suffix('qmark')),
      Right(Adjacency()),
    )),
  drop=('spaces',))

utest(('?', ('a', 'b')), right_qmark_adj.parse, 'expr', Source('', 'a b ?'))


