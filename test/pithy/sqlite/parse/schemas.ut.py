# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.io import outL, outM
from pithy.sqlite.parse import Source, sql_parser
from pithy.sqlite.schema import Column, Index, Schema, Table
from pithy.sqlite.util import nonstrict_to_strict_types_for_sqlite
from pithy.transtruct import TranstructorError
from utest import utest


s1 = Schema('s1',
  desc='s1 test schema.',
  structures=[

    Table('Meta',
      is_strict=True,
      without_rowid=True,
      columns=(
        Column(name='key', allow_kw=True, datatype=str, is_primary=True, is_unique=True, desc='The string key.'),
        Column(name='val', datatype=object, is_opt=True, desc='The value, whose type is treated as dynamic.'),
    )),

  Table('Privilege',
    desc='A user privilege.',
    is_strict=True,
    columns=(
      Column(name='id', datatype=int, is_primary=True, is_unique=True),
      Column(name='name', datatype=str, is_unique=True),
      Column(name='description', datatype=str, default=''),
  )),

  Table('User',
    is_strict=True,
    columns=(
      Column(name='id', datatype=int, is_primary=True, is_unique=True),
      Column(name='email', datatype=str, is_unique=True),
      Column(name='name', datatype=str, is_unique=True),
      Column(name='is_active', datatype=bool),
      Column(name='role', datatype=str),
  )),

  Index('User_email', table='User', columns=('email',)),

  Table('UserPrivilege',
    is_strict=True,
    without_rowid=True,
    primary_key=('user_id', 'privilege_id'),
    columns=(
      Column(name='user_id', datatype=int),
      Column(name='privilege_id', datatype=int),
  )),
  ]
)


def plan_migration(table:Table, current_sql:str) -> None:
  pass


def test_schema_parse(table:Table) -> None:
  sql = table.sql()
  sql_lines = sql.split('\n')
  source = Source(name=table.name, text=sql)
  ast = sql_parser.parse('create_stmt', source)
  try:
    parsed_table = Table.parse(table.name, sql)
  except TranstructorError as e:
    print('\nSQL:', *[f'{n:02}| {line}' for n, line in enumerate(sql_lines, 1)], sep='\n')
    outM('\nAST', ast, color=True)
    raise e

  if hints := table.diff_hints(parsed_table):
    outL('\nParsed table does not match original table.')
    outM('\nOriginal', table)
    outM('\nParsed', parsed_table)
    for pc, oc in zip(parsed_table.columns, table.columns):
      if pc.name != oc.name: break
      if pc != oc:
        outM('Orig Column', oc, color=True)
        outM('Parsed Column', pc, color=True)


for i, table in enumerate(s1.tables):
  test_schema_parse(table)
