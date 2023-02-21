#!/usr/bin/env python3

from pithy.parse import (Atom, Choice, Infix, Left, Opt, Parser, Precedence, ZeroOrMore, Struct, binary_to_list, choice_syn,
  atom_text, struct_syn)
from pithy.py.lex import lexer
from tolkien import Source, Token
from utest import *


basic = Parser(lexer,
  drop=('newline', 'spaces'),
  literals=('kw_as', 'kw_import', 'kw_from'),
  rules=dict(
    name=Atom('name', transform=atom_text),

    import_=Choice('import_modules', 'import_from', transform=choice_syn),
    import_modules=Struct('kw_import', 'path_as_exprs'),
    import_from=Struct('kw_from', 'path', 'kw_import', 'name_as_exprs', transform=lambda s, t, p: (p[1], p[3])),

    path_as_exprs=ZeroOrMore('path_as_expr', sep='comma'),
    path_as_expr=Struct('path', 'as_name', transform=struct_syn),

    name_as_exprs=ZeroOrMore('name_as_expr', sep='comma'),
    name_as_expr=Struct('name', 'as_name', transform=struct_syn),
    as_name=Opt(Struct('kw_as', 'name')),
    path=Precedence(
      ('name',),
      Left(Infix('dot', transform=binary_to_list)),
    )))


utest(('import_modules', [('m', '_m'), ('n', None)]),
  basic.parse,
  'import_', Source('', 'import m as _m, n'))

utest(('import_from', (['m','n','o'], [('a', None), ('b', '_b')])),
  basic.parse,
  'import_', Source('', 'from m.n.o import a, b as _b'))
