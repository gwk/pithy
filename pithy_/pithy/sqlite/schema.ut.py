# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.sqlite.schema import Column, Schema, Table
from utest import utest, utest_seq


nameless = Schema('', structures=[Table('t', columns=(Column('a', int),))])

# A name override produces the schema header comment and qualifies the structure names.
utest_seq(['\n', '-- Schema: x\n', '\n', 'CREATE TABLE x."t" (\n  a INTEGER NOT NULL\n)', ';', '\n'],
  nameless.sql, name='x', comments=True)

utest_seq(['\n', 'CREATE TABLE x."t" (\n  a INTEGER NOT NULL\n)', ';', '\n'], nameless.sql, name='x', comments=False)

utest_seq(['\n', 'CREATE TABLE "t" (\n  a INTEGER NOT NULL\n)', ';', '\n'], nameless.sql, comments=True)


# Signed numeric defaults parse back to the declared values.
utest(Table('t', columns=(Column('i', int, default=-1), Column('f', float, default=-1.5), Column('p', int, default=1))),
  Table.parse, 't',
  'CREATE TABLE t (i INTEGER NOT NULL DEFAULT -1, f REAL NOT NULL DEFAULT -1.5, p INTEGER NOT NULL DEFAULT +1)')

# A float default need not contain a decimal point.
utest(Table('t', columns=(Column('f', float, default=1e-09), Column('g', float, default=1e+16))),
  Table.parse, 't', 'CREATE TABLE t (f REAL NOT NULL DEFAULT 1e-09, g REAL NOT NULL DEFAULT 1e+16)')

# A hex integer default converts to its value.
utest(Table('t', columns=(Column('h', int, default=16), Column('n', int, default=-16))),
  Table.parse, 't', 'CREATE TABLE t (h INTEGER NOT NULL DEFAULT 0x10, n INTEGER NOT NULL DEFAULT -0x10)')

# A bool default renders as an SQL keyword.
utest('b INTEGER NOT NULL DEFAULT TRUE', Column('b', bool, default=True).sql)
utest('b INTEGER NOT NULL DEFAULT FALSE', Column('b', bool, default=False).sql)

# Keyword defaults parse in any case; a `CURRENT_` keyword converts to its canonical upper case.
utest(Table('t', columns=(Column('b', int, default=True), Column('d', str, default='CURRENT_DATE'))),
  Table.parse, 't', 'CREATE TABLE t (b INTEGER NOT NULL DEFAULT True, d TEXT NOT NULL DEFAULT current_date)')

# String and expression defaults remain SQL text; the empty SQL string converts to the empty string shorthand.
utest(Table('t', columns=(
    Column('s', str, default="'it''s'"), Column('e', str, default="('a' || 'b')"), Column('z', str, default=''))),
  Table.parse, 't',
  "CREATE TABLE t (s TEXT NOT NULL DEFAULT 'it''s', e TEXT NOT NULL DEFAULT ('a' || 'b'), z TEXT NOT NULL DEFAULT '')")
