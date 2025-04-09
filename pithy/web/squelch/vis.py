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
  join:str = '' # The schema.table.column to join on, typically the primary key.
  col:str = '' # The column in the joined table to display instead of the actual column.
  schema:str = ''
  table:str = ''
  join_col:str = ''
  render:Callable[[Any],Any]|None = None
  renders_row:bool = False


  def __post_init__(self) -> None:
    if self.join or self.col:
      if not (self.join and self.col): raise ValueError(f'`join` requires that `col` is also specified: {self}')
      s, t, c = sql_parse_schema_table_column(self.join)
      if not (t and c): raise ValueError(f'`join` must specify table and column (schema optional): {self.join!r}')
      _setattr(self, 'schema', s)
      _setattr(self, 'table', t)
      _setattr(self, 'join_col', c)


  def __repr__(self) -> str:
    return f'Vis(join={self.join!r}, col={self.col!r})'


  @cached_property
  def schema_table(self) -> str:
    return qqe(self.schema, self.table)
