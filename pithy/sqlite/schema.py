# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass, field
from functools import cached_property
from typing import Iterable

from .util import py_to_sqlite_types, sql_comment_inline, sql_comment_lines, sql_quote_entity


@dataclass
class Column:
  name:str
  datatype:type # Note: 'ANY' columns should be expressed with `object` rather than `Any` to mollify the type checker.
  is_opt:bool = False # Whether the column allows NULL. Must be False for primary keys.
  is_primary:bool = False # Whether the column is PRIMARY KEY.
  is_unique:bool = False # Whether the column is UNIQUE.
  desc:str = ''

  def __post_init__(self) -> None:
    if self.is_primary:
      if self.is_opt: raise ValueError(f'Primary key column {self} cannot be optional.')
      if not self.is_unique: raise ValueError(f'Primary key column {self} must be unique.')



class Structure:
  'Top-level SQL objects, i.e. Index, Table, Trigger, View.'

  name:str
  desc:str

  def sql(self, schema='', if_not_exists=False) -> str:
    raise NotImplementedError



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
    qual_name = f'{schema}{schema and "."}{sql_quote_entity(self.name)}'
    lines:list[str] = []
    if self.desc:
      lines.append(f'-- {qual_name}')
      lines.extend(sql_comment_lines(self.desc))
    if_not_exists_str = 'IF NOT EXISTS ' if if_not_exists else ''
    lines.append(f'CREATE TABLE {if_not_exists_str}{qual_name} (')

    # Colmuns are separated by commas, except for the last one.
    # This is complicated by comments following commas,
    # and trailing primary/foreign key lines that are also included within the parens.
    inner_parts = [] # Parts of lines within the parens.
    for c in self.columns:
      primary_key = ' PRIMARY KEY' if c.is_primary else ''
      not_null = '' if (c.is_opt or c.is_primary) else ' NOT NULL'
      comment = sql_comment_inline(c.desc) if c.desc else ''
      inner_parts.append(
        ['  ', sql_quote_entity(c.name), ' ', py_to_sqlite_types[c.datatype], primary_key, not_null, ',', comment])

    if self.primary_key:
      primary_key_parts = ', '.join(sql_quote_entity(c) for c in self.primary_key)
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
    lines.append(f'){table_options_str};')

    return '\n'.join(lines)


@dataclass
class Index(Structure):
  name:str
  table:str
  is_unique:bool = False
  desc:str = ''
  columns:tuple[str,...] = ()


  def sql(self, schema='', if_not_exists=False) -> str:
    qual_name = f'{schema}{schema and "."}{sql_quote_entity(self.name)}'
    lines = []
    if self.desc:
      lines.append(f'-- {qual_name}')
      lines.extend(sql_comment_lines(self.desc))

    if_not_exists_str = 'IF NOT EXISTS ' if if_not_exists else ''
    unique_str = 'UNIQUE ' if self.is_unique else ''
    lines.append(f'CREATE {unique_str}INDEX {if_not_exists_str}{qual_name}')
    columns_str = ', '.join(sql_quote_entity(c) for c in self.columns)
    lines.append(f'  ON {sql_quote_entity(self.table)} ({columns_str});')
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


  def structures_dict(self) -> dict[str, Structure]:
    return {s.name: s for s in self.structures}


  def sql(self, if_not_exists=False) -> Iterable[str]:

    if self.name or self.desc:
      yield '\n'
      if self.name: yield f'-- Schema: {self.name}\n'
      if self.desc: yield '\n'.join(sql_comment_lines(self.desc)) + '\n'

    for s in self.structures:
      yield '\n'
      yield s.sql(schema=self.name, if_not_exists=if_not_exists)
      yield '\n'


  def write_module_sql(self, if_not_exists=False, steps=1) -> None:
    '''
    Write an SQL schema file for this schema to the packge directory of the caller.
    This is typically callled from the main() of a module defining a schema.
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
