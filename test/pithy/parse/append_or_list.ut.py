# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.parse import Atom, atom_text, Infix, Left, left_binary_to_list, Parser, Precedence, Right, right_binary_to_stack
from pithy.py.lex import lexer
from pithy.stack import Stack
from tolkien import Source
from utest import utest


linked_lists = Parser(lexer,
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

utest('x', linked_lists.parse, 'expr', Source('', 'x'))

utest(['a', 'b', 'c', 'd'], linked_lists.parse, 'expr', Source('', 'a < b < c < d'))

utest(Stack(['w', 'x', 'y', 'z']), linked_lists.parse, 'expr', Source('', 'w > x > y > z'))
