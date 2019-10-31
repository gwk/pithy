#!/usr/bin/env python3

from pithy.parse import Atom, Choice, Infix, Left, Opt, Parser, Precedence, Struct, Quantity, token_extract_text
from pithy.py.lex import lexer
from tolkien import Source
from utest import *


basic = Parser(lexer, dict(
    name=Atom('name', transform=token_extract_text),
    kw_as=Atom('kw_as', transform=token_extract_text),
    kw_import=Atom('kw_import', transform=token_extract_text),
    kw_from=Atom('kw_from', transform=token_extract_text),

    import_=Choice('import_modules', 'import_from'),
    import_modules=Struct('kw_import', 'path_as_exprs'),
    import_from=Struct('kw_from', 'name', 'kw_import', 'name_as_exprs'),

    path_as_exprs=Quantity('path_as_expr', sep='comma'),
    path_as_expr=Struct('path', Opt(Struct('kw_as', 'name'))),

    name_as_exprs=Quantity('name_as_expr', sep='comma'),
    name_as_expr=Struct('name', Opt(Struct('kw_as', 'name'))),

    path=Precedence(
      ('name',),
      Left(Infix('dot')),
    )),
  drop=('newline', 'spaces'))


utest(('import_modules', ('import', [('m', ('as', '_m')), ('n', None)])),
  basic.parse, 'import_', Source('', 'import m as _m, n'))

utest(('import_from', ('from', 'm', 'import', [('a', None), ('b', ('as', '_b'))])),
  basic.parse, 'import_', Source('', 'from m import a, b as _b'))
