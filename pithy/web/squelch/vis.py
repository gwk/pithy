# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable

from pithy.sqlite.parse import sql_parse_schema_table_column

from ...html import Td
from ...sqlite.util import sql_quote_qual_entity as qqe


ValRenderFn = Callable[[Any],Any]
CellRenderFn = Callable[[Any],Td]
_setattr = object.__setattr__


@dataclass(frozen=True)
class Vis:
  show:bool = True # Whether to show the column by default.
  key:str = '' # The schema.table.column that this foreign key refers to, typically the other column's primary key.
  col:str = '' # The column in the joined table to display instead of the actual column.
  fk_schema:str = '' # Filled in automatically.
  fk_table:str = '' # Filled in automatically.
  fk_col:str = '' # Filled in automatically.
  render:Callable[[Any],Any]|None = None
  renders_row:bool = False


  def __post_init__(self) -> None:
    if self.key or self.col:
      if not (self.key and self.col): raise ValueError(f'`key` requires that `col` is also specified: {self}')
      s, t, c = sql_parse_schema_table_column(self.key)
      if not (t and c): raise ValueError(f'`key` must specify table and column (leading schema is optional): {self.key!r}')
      _setattr(self, 'fk_schema', s)
      _setattr(self, 'fk_table', t)
      _setattr(self, 'fk_col', c)


  def __repr__(self) -> str:
    return f'Vis(key={self.key!r}, col={self.col!r})'


  @cached_property
  def fk_schema_table(self) -> str:
    return qqe(self.fk_schema, self.fk_table)
