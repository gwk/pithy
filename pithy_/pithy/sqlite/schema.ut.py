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
  Table.parse, 't', 'CREATE TABLE t (i INTEGER NOT NULL DEFAULT -1, f REAL NOT NULL DEFAULT -1.5, p INTEGER NOT NULL DEFAULT +1)')

# A float default need not contain a decimal point.
utest(Table('t', columns=(Column('f', float, default=1e-09), Column('g', float, default=1e+16))),
  Table.parse, 't', 'CREATE TABLE t (f REAL NOT NULL DEFAULT 1e-09, g REAL NOT NULL DEFAULT 1e+16)')
