#!/usr/bin/env python3

from pithy.parse import (Atom, Choice, Infix, Left, Opt, Parser, Precedence, ZeroOrMore, Struct, binary_to_list, choice_syn,
  atom_text)
from pithy.py.lex import lexer
from tolkien import Source
from utest import *


basic = Parser(lexer,
  drop=('newline', 'spaces'),
  literals=('kw_as', 'kw_import', 'kw_from'),
  rules=dict(
    name=Atom('name', transform=atom_text),

    import_=Choice('import_modules', 'import_from', transform=choice_syn),
    import_modules=Struct('kw_import', 'path_as_exprs'),
    import_from=Struct('kw_from', 'path', 'kw_import', 'name_as_exprs'),

    path_as_exprs=ZeroOrMore('path_as_expr', sep='comma'),
    path_as_expr=Struct('path', 'as_name'),

    name_as_exprs=ZeroOrMore('name_as_expr', sep='comma'),
    name_as_expr=Struct('name', 'as_name'),
    as_name=Opt(Struct('kw_as', 'name')),
    path=Precedence(
      ('name',),
      Left(Infix('dot', transform=binary_to_list)),
    )))

Import_from = basic.types.Import_from

utest(('import_modules', [('m', '_m'), ('n', None)]),
  basic.parse,
  'import_', Source('', 'import m as _m, n'))

utest(
  ('import_from', Import_from(path=['m','n','o'], name_as_exprs=[('a', None), ('b', '_b')])),
  basic.parse,
  'import_', Source('', 'from m.n.o import a, b as _b'))
