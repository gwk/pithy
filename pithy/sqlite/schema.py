# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from functools import cached_property
from .util import sqlite_quote_entity, py_to_sqlite_types


@dataclass
class Column:
  name:str
  datatype:type
  is_primary:bool # Whether the column is PRIMARY KEY.
  is_required:bool # Whether the column is PRIMARY KEY or NOT NULL.
  desc:str = ''



@dataclass
class Table:
  name:str
  desc:str
  columns:dict[str,Column]
  primary_key:tuple[str,...] = () # The compound primary key, if any.
  # TODO: foreign keys.
  without_rowid:bool = False


  @cached_property
  def column_names_seq(self) -> tuple[str,...]: return tuple(self.columns.keys())

  @cached_property
  def column_names_set(self) -> frozenset[str]: return frozenset(self.columns.keys())


  def sql_create_stmt(self, if_not_exists=False, strict=False) -> str:
    if_not_exists_str = 'IF NOT EXISTS ' if if_not_exists else ''
    lines = [f'CREATE TABLE {if_not_exists_str}{self.name} (']

    # Colmuns are separated by commas, except for the last one.
    # This is complicated by comments following commas,
    # and primary/foreign key lines that are also within the parens.
    inner_parts = [] # Parts of lines within the parens.
    for c in self.columns.values():
      primary_key = ' PRIMARY KEY' if c.is_primary else ''
      not_null = ' NOT NULL' if not c.is_primary and c.is_required else ''
      comment = f' -- {c.desc}' if c.desc else ''
      inner_parts.append(
        ['  ', sqlite_quote_entity(c.name), ' ', py_to_sqlite_types[c.datatype], primary_key, not_null, ',', comment])

    if self.primary_key:
      primary_key_parts = ', '.join(sqlite_quote_entity(c) for c in self.primary_key)
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
