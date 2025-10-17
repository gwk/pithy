# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.parse import (Atom, atom_text, Infix, Left, left_binary_to_list, parse_skel, Parser, Precedence, Right,
  right_binary_to_stack)
from pithy.py.lex import lexer
from pithy.stack import Stack
from utest import utest


parser = Parser(lexer,
  drop=('newline', 'spaces'),
  literals=(),
  rules=dict(
    name=Atom('name', transform=atom_text),
    expr=Precedence(
      ('name'),
      Left(Infix('lt', transform=left_binary_to_list)),
      Right(Infix('gt', transform=right_binary_to_stack)),
    )
  ),
)

def parse(s:str) -> Any: return parse_skel(parser, 'expr', s)

utest('x', parse, 'x')

utest(['a', 'b', 'c', 'd'], parse, 'a < b < c < d')

utest(Stack(['w', 'x', 'y', 'z']), parse, 'w > x > y > z')
