# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.sqlite.schema import Column, Schema, Table
from utest import utest_seq


nameless = Schema('', structures=[Table('t', columns=(Column('a', int),))])

# A name override produces the schema header comment and qualifies the structure names.
utest_seq(['\n', '-- Schema: x\n', '\n', 'CREATE TABLE x."t" (\n  a INTEGER NOT NULL\n)', ';', '\n'],
  nameless.sql, name='x', comments=True)

utest_seq(['\n', 'CREATE TABLE x."t" (\n  a INTEGER NOT NULL\n)', ';', '\n'], nameless.sql, name='x', comments=False)

utest_seq(['\n', 'CREATE TABLE "t" (\n  a INTEGER NOT NULL\n)', ';', '\n'], nameless.sql, comments=True)
