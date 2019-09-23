#!/usr/bin/env python3

from pithy.parse import Atom, Choice, Infix, Left, Parser, Precedence, Struct, Quantity
from pithy.py.lex import lexer
from tolkien import Source
from utest import *


basic = Parser(lexer, dict(
    name=Atom('name'),
    kw_as=Atom('kw_as'),
    kw_import=Atom('kw_import'),
    kw_from=Atom('kw_from'),

    import_=Choice('import_modules', 'import_from'),
    import_modules=Struct('kw_import', 'as_exprs'),
    import_from=Struct('kw_from', 'name', 'kw_import', 'as_exprs'),

    as_exprs=Quantity('as_expr', sep='comma'),
    as_expr=Precedence(
      ('name',),
      Left(Infix('kw_as')), # TODO: these clauses should not be recursive.
      Left(Infix('dot')),
    )),
  drop=('newline', 'spaces'))


utest(('import_modules', ('import', [('as', 'm', '_m'), 'n'])),
  basic.parse, 'import_', Source('', 'import m as _m, n'))

utest(('import_from', ('from', 'm', 'import', ['a', ('as', 'b', '_b')])),
  basic.parse, 'import_', Source('', 'from m import a, b as _b'))
