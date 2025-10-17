# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.parse import (Atom, Choice, choice_labeled, Infix, Left, left_binary_to_list, Opt, parse_skel, Parser, Precedence,
  Struct, ZeroOrMore)
from pithy.py.lex import lexer
from utest import utest


basic = Parser(lexer,
  drop=('newline', 'spaces'),
  literals=('kw_as', 'kw_import', 'kw_from'),
  rules=dict(
    name=Atom('name'),

    import_=Choice('import_modules', 'import_from', transform=choice_labeled),
    import_modules=Struct('kw_import', 'path_as_exprs'),
    import_from=Struct('kw_from', 'path', 'kw_import', 'name_as_exprs'),

    path_as_exprs=ZeroOrMore('path_as_expr', sep='comma'),
    path_as_expr=Struct('path', 'as_name'),

    name_as_exprs=ZeroOrMore('name_as_expr', sep='comma'),
    name_as_expr=Struct('name', 'as_name'),
    as_name=Opt(Struct('kw_as', 'name')),
    path=Precedence(
      ('name',),
      Left(Infix('dot', transform=left_binary_to_list)),
    ),
  ),
)


utest(('import_modules', [('m', '_m'), ('n', None)]), parse_skel, basic, 'import_', 'import m as _m, n')

utest(('import_from', (['m','n','o'], [('a', None), ('b', '_b')])),
  parse_skel, basic, 'import_', 'from m.n.o import a, b as _b')
