# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Iterable

from tolkien import Source, Token

from ..transtruct import Ctx, Input, Transtructor
from .keywords import sqlite_keywords
from .parse import parser
from .util import (py_to_sqlite_types, sql_comment_inline, sql_comment_lines, sql_quote_entity_always, sql_unquote_entity,
  sql_unquote_str, sqlite_py_type_ambiguities, sqlite_to_py_types)


@dataclass
class Column:
  '''
  `default`: must be either a `signed-number`, `literal-value`, 'CURRENT_TIME', 'CURRENT_DATE', 'CURRENT_TIMESTAMP', or an SQL `expr`.
  SQLite column constraints: https://www.sqlite.org/syntax/column-constraint.html

  We use `sql_quote_entity_always` to quote all column names because this is SQLite currently always quotes renamed columns.
  By quoting names in the generated statements, we eliminate sytnactic discrepancies caused by rename operations.
  '''
  name:str
  datatype:type # Note: 'ANY' columns should be expressed with `object` rather than `Any` to mollify the type checker.
  allow_kw:bool = False # Whether the column name is allowed to be a keyword.
  is_opt:bool = False # Whether the column allows NULL. Must be False for primary keys.
  is_primary:bool = False # Whether the column is PRIMARY KEY.
  is_unique:bool = False # Whether the column is UNIQUE.
  virtual:str|None = None
  default:int|float|str|None = None # The default value. None means no default; SQLite will default to NULL.
  desc:str = ''

  @cached_property
  def is_non_opt_str(self) -> bool: return self.datatype is str and not self.is_opt


  def __post_init__(self) -> None:
    if not self.allow_kw and self.name.upper() in sqlite_keywords:
      raise ValueError(f'Column name {self.name!r} is an SQLite keyword. Use `allow_kw=True` to override.')
    if self.is_primary:
      if self.is_opt: raise ValueError(f'Primary key column {self} cannot be optional.')
      if not self.is_unique: raise ValueError(f'Primary key column {self} must be unique.')
    if self.virtual is not None:
      if self.is_primary: raise ValueError(f'Virtual column {self} cannot be primary key.')
      if self.default is not None: raise ValueError(f'Virtual column {self} cannot have a default value.')

  def sql(self) -> str:
    name = sql_quote_entity_always(self.name)
    type_ = py_to_sqlite_types[self.datatype]
    primary_key = ' PRIMARY KEY' if self.is_primary else ''
    unique = ' UNIQUE' if self.is_unique else ''
    not_null = '' if (self.is_opt or self.is_primary) else ' NOT NULL'

    if self.default is not None:
      d = self.default
      if isinstance(d, (int, float)): ds = str(self.default)
      else:
        assert isinstance(d, str)
        if d == '': ds = "''" # Special affordance for the empty string as shorthand.
        elif d.startswith("'") and d.endswith("'"): ds = d # Quoted string value.
        elif d.startswith('(') and d.endswith(')'): ds = d # SQL expression.
        elif d in ('CURRENT_TIME', 'CURRENT_DATE', 'CURRENT_TIMESTAMP'): ds = d # Special value.
        else: raise ValueError(f'Invalid Column default SQL expression: {d!r}')
      default = f' DEFAULT {ds}'
    elif self.virtual is not None:
      default = f' AS ({self.virtual}) VIRTUAL'
    else:
      default = ''

    return f'{name} {type_}{primary_key}{unique}{not_null}{default}'


class Structure:
  'Top-level SQL objects, i.e. Index, Table, Trigger, View.'

  name:str
  desc:str

  def sql(self, schema='', if_not_exists=False) -> str:
    raise NotImplementedError

  @classmethod
  def parse(cls, path:str, text:str) -> 'Structure':
    '''
    Parse a schema definition from a string.
    '''
    source = Source(path, text)
    ast = parser.parse('create_stmt', source)
    return schema_transtructor.transtruct(cls, ast, ctx=source)


@dataclass
class Table(Structure):
  name:str
  desc:str = ''
  is_strict:bool = False
  without_rowid:bool = False
  primary_key:tuple[str,...] = () # The compound primary key, if any.
  # TODO: foreign keys.
  columns:tuple[Column,...] = ()


  @cached_property
  def columns_dict(self) -> dict[str, Column]: return {c.name: c for c in self.columns}

  @cached_property
  def column_names(self) -> tuple[str, ...]: return tuple(c.name for c in self.columns)


  def sql(self, schema='', if_not_exists=False) -> str:
    qual_name = f'{schema}{schema and "."}{sql_quote_entity_always(self.name)}'
    lines:list[str] = []
    if_not_exists_str = 'IF NOT EXISTS ' if if_not_exists else ''
    lines.append(f'CREATE TABLE {if_not_exists_str}{qual_name} (')
    if self.desc: lines.extend(sql_comment_lines(self.desc, indent='  '))

    # Colmuns are separated by commas, except for the last one.
    # This is complicated by comments following commas,
    # and trailing primary/foreign key lines that are also included within the parens.
    inner_parts = [] # Parts of lines within the parens.
    for c in self.columns:
      column_sql = c.sql()
      comment = sql_comment_inline(c.desc) if c.desc else ''
      inner_parts.append(['  ', column_sql, ',', comment])

    if self.primary_key:
      primary_key_parts = ', '.join(sql_quote_entity_always(c) for c in self.primary_key)
      inner_parts.append([f'  PRIMARY KEY ({primary_key_parts})', ',', ''])

    # Remove the comma from the last inner line.
    assert inner_parts[-1][-2] == ','
    inner_parts[-1][-2] = '' # Remove last comma.

    lines.extend(''.join(p) for p in inner_parts)

    table_options = [
      ' STRICT' if self.is_strict else '',
      ' WITHOUT ROWID' if self.without_rowid else '',
    ]
    table_options_str = ','.join(opt for opt in table_options if opt)
    lines.append(f'){table_options_str}')

    return '\n'.join(lines)


@dataclass
class Index(Structure):
  name:str
  table:str
  is_unique:bool = False
  desc:str = ''
  columns:tuple[str,...] = ()


  def sql(self, schema='', if_not_exists=False) -> str:
    qual_name = f'{schema}{schema and "."}{sql_quote_entity_always(self.name)}'
    lines = []
    if self.desc:
      lines.append(f'-- {qual_name}')
      lines.extend(sql_comment_lines(self.desc))

    if_not_exists_str = 'IF NOT EXISTS ' if if_not_exists else ''
    unique_str = 'UNIQUE ' if self.is_unique else ''
    lines.append(f'CREATE {unique_str}INDEX {if_not_exists_str}{qual_name}')
    columns_str = ', '.join(sql_quote_entity_always(c) for c in self.columns)
    lines.append(f'  ON {sql_quote_entity_always(self.table)} ({columns_str})')
    return '\n'.join(lines)



@dataclass
class Schema:
  name:str = ''
  desc:str = ''
  tables:list[Table] = field(default_factory=list)
  indexes:list[Index] = field(default_factory=list)


  def __post_init__(self) -> None:
    names = set()
    for s in self.structures:
      if s.name in names: raise ValueError(f'Structure {s} has a duplicate name.')
      names.add(s.name)


  @property
  def structures(self) -> Iterable[Structure]:
    yield from self.tables
    yield from self.indexes


  @cached_property
  def structures_dict(self) -> dict[str, Structure]:
    return {s.name: s for s in self.structures}


  @cached_property
  def tables_dict(self) -> dict[str, Table]:
    return {t.name: t for t in self.tables}


  @cached_property
  def indexes_dict(self) -> dict[str, Index]:
    return {i.name: i for i in self.indexes}


  def sql(self, if_not_exists=False) -> Iterable[str]:

    if self.name or self.desc:
      yield '\n'
      if self.name: yield f'-- Schema: {self.name}\n'
      if self.desc: yield '\n'.join(sql_comment_lines(self.desc)) + '\n'

    for s in self.structures:
      yield '\n'
      yield s.sql(schema=self.name, if_not_exists=if_not_exists)
      yield ';'
      yield '\n'


  def write_module_sql(self, if_not_exists=False, steps=1) -> None:
    '''
    Write an SQL schema file for this schema to the packge directory of the caller.
    This is typically called from the main() of a module defining a schema.
    `steps` can be used to adjust the frame introspection level.
    Be careful: if the step count is wrong, the file may be written into an installed package location,
    which is usually not desirable and potentially destructive to the installation.
    '''
    from ..meta import caller_module_spec
    if steps < 1: raise ValueError(f'steps must be >= 1; received {steps!r}')
    spec = caller_module_spec(steps=steps)
    path = spec.origin
    if not path: raise ValueError(f'Cannot determine path of caller module: {spec!r}.')
    if not path.endswith('.py'): raise ValueError(f'Expected a .py file for module; {spec!r}')
    path = path[:-3] + '.sql'
    print(f'Writing SQL schema to {path!r}.')
    with open(path, 'w') as f:
      f.write(''.join(self.sql(if_not_exists=if_not_exists)))


  @classmethod
  def parse(cls, path:str, text:str) -> 'Schema':
    '''
    Parse a schema definition from a string.
    '''
    source = Source(path, text)
    ast = parser.parse('stmts', source)
    return schema_transtructor.transtruct(Schema, ast, ctx=source)


schema_transtructor = Transtructor()


@schema_transtructor.prefigure(Column)
def prefigure_Column(class_:type, column:Input, source:Source) -> dict[str,Any]:
  name = sql_unquote_entity(source[column.name])
  if column.type_name is None: raise ValueError(f'Column {name!r} has no type.')
  type_name = source[column.type_name]
  datatype = sqlite_to_py_types[type_name]
  constraints = dict(_parse_column_constraint(cc, source) for cc in column.constraints)
  is_primary = constraints.get('primary_key', False)
  is_opt = not constraints.get('not_null', False) and not is_primary
  is_unique = constraints.get('unique', False) or is_primary
  return dict(
    name=name,
    datatype=datatype,
    allow_kw=(name.upper() in sqlite_keywords),
    is_opt=is_opt,
    is_primary=is_primary,
    is_unique=is_unique,
    virtual=None,
    default=constraints.get('default'),
  )


def _parse_column_constraint(constraint:Input, source:Source) -> tuple[str,Any]:
  if constraint.constraint_name is not None: raise NotImplementedError(f'column_constraint named constraint: {constraint.constraint_name!r}')
  label, val = constraint.kind
  match label:
    case 'primary_key':
      if val.asc_desc is not None: raise NotImplementedError(f'column_constraint primary_key asc_desc: {constraint!r}')
      if val.on_conflict is not None: raise NotImplementedError(f'column_constraint primary_key on_conflict: {constraint!r}')
      if val.AUTOINCREMENT is not None: raise NotImplementedError(f'column_constraint primary_key autoincrement: {constraint!r}')
      return label, True
    case 'not_null' | 'unique':
      on_conflict = val
      if on_conflict is not None: raise NotImplementedError(f'column_constraint primary_key on_conflict: {constraint!r}')
      return label, True
    case 'check':
      raise NotImplementedError(f'column_constraint check: {constraint!r}')
    case 'default':
      return label, _parse_column_default(val, source)
    case 'collate':
      raise NotImplementedError(f'column_constraint collate: {constraint!r}')
    case 'generated_constraint':
      raise NotImplementedError(f'column_constraint generated_constraint: {constraint!r}')
    case _:
      raise NotImplementedError(f'column_constraint: {constraint!r}')


def _parse_column_default(default:Input, source:Source) -> Any:
  'int|float|str|None'
  label, val = default
  match label:
    case 'paren_expr': raise NotImplementedError
    case 'literal_value': return sql_unquote_str(source[val])
    case 'signed_number': return source[val.sign] + source[val.number]



@schema_transtructor.prefigure(Table)
def prefigure_Table(class_:type, table:Input, source:Source) -> dict[str,Any]:
  table_name_parts = [sql_unquote_entity(source[t]) for t in table.name]

  def_ = table.def_
  if not isinstance(def_, parser.types.TableDef): raise ValueError(f'Expected a table_def; received {def_!r}')
  column_defs = def_.column_defs
  constraints = dict(_parse_table_constraint(tc, source) for tc in def_.table_constraints)
  table_options = def_.table_options

  return dict(
    name=table_name_parts[-1], # NOTE: we currently discard the schema name if it is present.
    is_strict=('STRICT' in table_options),
    without_rowid=('WITHOUT ROWID' in table_options),
    primary_key=constraints.get('primary_key', ()),
    columns=column_defs,
  )


def _parse_table_constraint(constraint:Input, source:Source) -> tuple[str,Any]:
  if constraint.constraint_name is not None: raise NotImplementedError(f'Cannot parse constraint_name: {constraint.constraint_name!r}')
  label, val = constraint.kind
  match label:
    case 'primary_key':
      col_names = tuple(_parse_indexed_column(c, source) for c in val.indexed_columns)
      if val.on_conflict is not None: raise NotImplementedError(f'Cannot parse on_conflict: {val.on_conflict!r}')
      return label, col_names
    case _: raise NotImplementedError(f'Cannot parse table constraint {label!r}: {constraint!r}')


def _parse_indexed_column(column:Input, source:Source) -> str:
  expr = column.expr
  assert column.collate is None
  assert column.asc_desc is None
  assert isinstance(expr, list) and len(expr) == 1
  return sql_unquote_entity(source[expr[0]])


def clean_row_record(table:Table, renamed_keys:dict[str,str]|None, record:dict[str,Any]) -> dict[str,Any]:
  '''
  Clean a record dict in preparation for inserting it into a database table.
  `renamed_keys`  maps the record key to the desired table column name.
  '''
  columns_dict = table.columns_dict
  def replace_none_with_empty(k:str, v:Any) -> Any:
    return '' if v is None and columns_dict[k].is_non_opt_str else v

  if renamed_keys:
    return { renamed_keys.get(k,k): replace_none_with_empty(k, v)
      for k, v in record.items() if k in columns_dict or k in renamed_keys }
  else:
    return { k: replace_none_with_empty(k, v) for k, v in record.items() if k in columns_dict }
