# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from contextlib import AbstractContextManager
from typing import Any, cast, Iterable, Mapping, overload, Protocol, Self, Sequence, TypeAlias, TypeVar

from ..typing_utils import OptBaseExc, OptTraceback, OptTypeBaseExc
from .row import Row
from .util import default_to_json, insert_values_stmt, sql_quote_entity, update_stmt, update_to_json


_T_co = TypeVar('_T_co', covariant=True)

class _SupportsLenAndGetItemByInt(Protocol[_T_co]):
  def __len__(self) -> int: ...
  def __getitem__(self, __k:int) -> _T_co: ...

_ReadableBuffer:TypeAlias = bytes | bytearray | memoryview # | array.array[Any] | mmap.mmap | ctypes._CData | pickle.PickleBuffer

_SqliteData:TypeAlias = str | _ReadableBuffer | int | float | None

_AdaptedInputData:TypeAlias = _SqliteData | Any
#^ Data that is passed through adapters can be of any type accepted by an adapter.

SqlParameters: TypeAlias = _SupportsLenAndGetItemByInt[_AdaptedInputData] | Mapping[str, _AdaptedInputData]
#^ The Mapping must really be a dict, but making it invariant is too annoying.


class Cursor(sqlite3.Cursor, AbstractContextManager):


  def __enter__(self) -> Self:
    '''
    On context manager enter, Cursor begins a transaction.
    '''
    self.execute('BEGIN')
    return self


  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> None:
    '''
    On context manager exit, Cursor commits or rolls back, then closes itself.
    '''
    if exc_type: # Exception raised.
      self.execute('ROLLBACK')
    else:
      self.execute('COMMIT')
    self.close()


  def execute(self, query:str, args:SqlParameters=()) -> Self:
    '''
    Execute a single SQL statement, optionally binding Python values using placeholders.

    Override execute in order to set `query` on any resulting sqlite3.Error.
    '''
    try: return super().execute(query, args)
    except sqlite3.Error as e:
      setattr(e, 'query', query)
      e.add_note(f'query: {query}')
      raise


  def executemany(self, query:str, it_args:Iterable[SqlParameters]) -> Self:
    '''
    For every item in `it_args`, repeatedly execute the parameterized DML SQL statement sql.

    Override executemany in order to set `query` on any resulting sqlite3.Error.
    '''
    try: return super().executemany(query, it_args)
    except sqlite3.Error as e:
      setattr(e, 'query', query)
      e.add_note(f'query: {query}')
      raise


  def executescript(self, sql_script:str) -> Self:
    '''
    Execute the SQL statements in sql_script. If the autocommit is LEGACY_TRANSACTION_CONTROL and there is a pending transaction, an implicit COMMIT statement is executed first. No other implicit transaction control is performed; any transaction control must be added to sql_script.

    Override executemany in order to set `query` on any resulting sqlite3.Error.
    '''
    try: return cast(Self, super().executescript(sql_script))
    except sqlite3.Error as e:
      setattr(e, 'query', sql_script)
      e.add_note(f'script: {sql_script}')
      raise


  def run(self, sql:str, *, _dbg=False, **args:Any) -> Self:
    '''
    Execute a query with parameter values provided by keyword arguments.
    Argument values whose types are not sqlite-compatible are automatically converted to JSON.
    '''
    args = update_to_json(args)
    if _dbg: print(f'query: {sql.strip()}\n  args: {args}')
    return self.execute(sql, args)


  def opt(self) -> Row|None:
    'Return a single, optional row.'
    return cast(Row|None, self.fetchone())


  def one(self) -> Row:
    'Return a single, non-optional row.'
    row = self.fetchone()
    if row is None: raise ValueError(None)
    return cast(Row, row)


  def col(self) -> Iterable[Any]:
    'Yield column 0 of each result row.'
    row = self.fetchone()
    if row is None: return
    assert len(row) == 1
    yield row[0]
    for row in self:
      yield row[0]


  def opt_col(self, default:Any=None) -> Any:
    if row := self.fetchone():
      assert len(row) == 1
      return row[0]
    else:
      return default


  def one_col(self) -> Any:
    row = self.fetchone()
    if row is None: raise ValueError(None)
    assert len(row) == 1
    return row[0]


  def contains(self, table:str, *, where:str, **args:Any) -> bool:
    'Execute a SELECT query, returning True if the `where` SQL clause results in at least one row.`'

    for _ in self.execute(f'SELECT 1 FROM {table} WHERE {where} LIMIT 1', args):
      return True
    return False


  def count(self, table:str, *, where='', **args:Any) -> int:
    'Execute a SELECT COUNT() query, returning the number of rows.'
    where_clause = f' WHERE {where}' if where else ''
    for row in self.execute(f'SELECT COUNT() FROM {table}{where_clause}', args):
      return row[0] # type: ignore[no-any-return]
    raise Exception(f'No row returned from COUNT query: {table}{where_clause}')


  @overload
  def insert(self, *, with_='', or_='FAIL', into:str, returning:tuple[str,...], **kwargs:Any) -> Row: ...

  @overload
  def insert(self, *, with_='', or_='FAIL', into:str, returning:str, **kwargs:Any) -> Any: ...

  @overload
  def insert(self, *, with_='', or_='FAIL', into:str, returning:None=None, **kwargs:Any) -> None: ...

  def insert(self, *, with_='', or_='FAIL', into:str, returning:tuple[str,...]|str|None=None, _dbg=False, **kwargs:Any):
    '''
    Execute an insert statement with the kwargs key/value pairs passed as named arguments.
    If `returning` is a tuple, return a single row; if it is a string, return a single column.
    '''
    stmt = insert_values_stmt(with_=with_, or_=or_, into=into, named=True, fields=tuple(kwargs.keys()), returning=returning)
    self.run(stmt, _dbg=_dbg, **kwargs)

    if isinstance(returning, tuple): return self.one()
    elif isinstance(returning, str): return self.one_col()
    else: return None


  @overload
  def insert_dict(self, *, with_='', or_='FAIL', into:str, fields:Iterable[str]|None=None, returning:tuple[str,...],
   args:dict[str, Any], defaults:dict[str,Any]=...) -> Row: ...

  @overload
  def insert_dict(self, *, with_='', or_='FAIL', into:str, fields:Iterable[str]|None=None, returning:str,
   args:dict[str,Any], defaults:dict[str,Any]=...) -> Any: ...

  @overload
  def insert_dict(self, *, with_='', or_='FAIL', into:str, fields:Iterable[str]|None=None,returning:None=None,
   args:dict[str,Any], defaults:dict[str,Any]=...) -> None: ...

  def insert_dict(self, *, with_='', or_='FAIL', into:str, fields:Iterable[str]|None=None, returning:tuple[str,...]|str|None=None,
   args:dict[str,Any], defaults:dict[str,Any]={}) -> Any:
    '''
    Execute an insert of the dictionary `args`, synthesized from `into` (the table name) and `fields`.
    Values are pulled in by name first from the `args` dictionary, then from `defaults`;
    a KeyError is raised if one of the fields is not provided in either of these sources.
    If `returning` is a tuple, return a single row; if it is a string, return a single column.
    TODO: support json.
    '''
    if fields is None: fields = args.keys()
    stmt = insert_values_stmt(with_=with_, or_=or_, into=into, named=False, fields=tuple(fields), returning=returning)

    def arg_for(f:str) -> Any:
      try: return args[f]
      except KeyError: pass
      return defaults[f]

    values = [default_to_json(arg_for(f)) for f in fields]

    self.execute(stmt, values)

    if isinstance(returning, tuple): return self.one()
    elif isinstance(returning, str): return self.one_col()
    else: return None


  def insert_seq(self, *, with_='', or_='FAIL', into:str, fields:Iterable[str], seq:Sequence[Any]) -> None:
    '''
    Execute an insert of the sequence `args`, synthesized from `into` (the table name), and `fields`.
    '''
    stmt = insert_values_stmt(with_=with_, or_=or_, into=into, named=False, fields=tuple(fields))
    values = [default_to_json(v) for v in seq]
    self.execute(stmt, values)


  def count_all_tables(self, *, schema:str='main', omit_empty=False) -> list[tuple[str, int]]:
    'Return an iterable of (table, count) pairs.'
    schema_q = sql_quote_entity(schema)
    table_names = list(self.execute(f"SELECT name FROM {schema_q}.sqlite_schema WHERE type = 'table' ORDER BY name").col())
    pairs = []
    for name in table_names:
      count = self.count(f'{schema_q}.{name}')
      if omit_empty and count == 0: continue
      pairs.append((name, count))
    return pairs


  def update(self, table:str, *, with_='', or_='FAIL', by:str|tuple[str,...], _dbg=False, **kwargs:Any) -> None:
    '''
    Execute an UPDATE statement.
    TODO: support returning clause.
    '''
    if isinstance(by, str): by = (by,)
    if not isinstance(by, tuple): raise TypeError('`by` argument must be a string or tuple of strings.')
    if not by: raise ValueError('`by` argument must not be empty for safety.')
    where = ' AND '.join(f'{sql_quote_entity(k)} = :{k}' for k in by)
    fields = tuple(k for k in kwargs if k not in by)
    stmt = update_stmt(with_=with_, or_=or_, table=table, named=True, fields=fields, where=where)
    self.run(stmt, _dbg=_dbg, **kwargs)
