# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from functools import cached_property
from .util import sql_quote_entity, py_to_sqlite_types


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


@dataclass
class Table:
  name:str
  desc:str = ''
  without_rowid:bool = False
  primary_key:tuple[str,...] = () # The compound primary key, if any.
  # TODO: foreign keys.
  columns:tuple[Column,...] = ()


  @cached_property
  def columns_dict(self) -> dict[str, Column]: return {c.name: c for c in self.columns}

  @cached_property
  def column_names(self) -> tuple[str, ...]: return tuple(c.name for c in self.columns)


  def sql_create_stmt(self, schema='', if_not_exists=False, strict=False) -> str:
    if_not_exists_str = 'IF NOT EXISTS ' if if_not_exists else ''
    schema_dot = '.' if schema else ''
    lines = [f'CREATE TABLE {if_not_exists_str}{schema}{schema_dot}{sql_quote_entity(self.name)} (']

    # Colmuns are separated by commas, except for the last one.
    # This is complicated by comments following commas,
    # and primary/foreign key lines that are also within the parens.
    inner_parts = [] # Parts of lines within the parens.
    for c in self.columns:
      primary_key = ' PRIMARY KEY' if c.is_primary else ''
      not_null = '' if (c.is_opt or c.is_primary) else ' NOT NULL'
      comment = f' -- {c.desc}' if c.desc else ''
      inner_parts.append(
        ['  ', sql_quote_entity(c.name), ' ', py_to_sqlite_types[c.datatype], primary_key, not_null, ',', comment])

    if self.primary_key:
      primary_key_parts = ', '.join(sql_quote_entity(c) for c in self.primary_key)
      inner_parts.append([f'  PRIMARY KEY ({primary_key_parts})', ',', ''])

    # Fix up the last inner line.
    assert inner_parts[-1][-2] == ','
    inner_parts[-1][-2] = '' # Remove last comma.

    lines.extend(''.join(p) for p in inner_parts)

    table_options = [
      ' STRICT' if strict else '',
      ' WITHOUT ROWID' if self.without_rowid else '',
    ]
    table_options_str = ','.join(opt for opt in table_options if opt)
    lines.append(f'){table_options_str};')

    return '\n'.join(lines)
