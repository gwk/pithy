# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from time import monotonic as get_time
from typing import Any, cast, Iterable, Mapping, overload, Protocol, Self, Sequence, TypeVar

from ..frozendicts import frozendict
from .row import Row
from .util import (insert_values_stmt, OnConflictTarget, sql_quote_entity, sql_substitute_exprs, SqlExpr, sqlite_datatypes,
  sqlite_native_val, update_stmt)


_T_co = TypeVar('_T_co', covariant=True)

class _SupportsLenAndGetItemByInt(Protocol[_T_co]):
  def __len__(self) -> int: ...
  def __getitem__(self, __k:int) -> _T_co: ...

type _ReadableBuffer = bytes | bytearray | memoryview # | array.array[Any] | mmap.mmap | ctypes._CData | pickle.PickleBuffer

type _SqliteData = str | _ReadableBuffer | int | float | None

type _AdaptedInputData = _SqliteData | Any
#^ Data that is passed through adapters can be of any type accepted by an adapter.

type SqlParameters = _SupportsLenAndGetItemByInt[_AdaptedInputData] | Mapping[str, _AdaptedInputData]
#^ The Mapping must really be a dict, but making it invariant is too annoying.


def _sqlite_native_args(args:SqlParameters) -> SqlParameters:
  '''
  Convert statement argument values to sqlite-native values using `sqlite_native_val`.
  Returns `args` unchanged if all values are already native; otherwise returns a new list or dict.
  '''
  if isinstance(args, Mapping):
    if all(isinstance(v, sqlite_datatypes) for v in args.values()): return args
    return { k: sqlite_native_val(v) for k, v in args.items() }
  if all(isinstance(args[i], sqlite_datatypes) for i in range(len(args))): return args
  return [sqlite_native_val(args[i]) for i in range(len(args))]


class Cursor(sqlite3.Cursor):

  execute_time:float = 0


  def execute(self, query:str, args:SqlParameters=()) -> Self:
    '''
    Execute a single SQL statement, optionally binding Python values using placeholders.
    Argument values are converted to sqlite-native values; see `sqlite_native_val`.
    Named `SqlExpr` argument values are substituted into the query as raw SQL.

    Override execute in order add `execute_time` and `query` attributes/notes on any resulting sqlite3.Error.
    '''
    if isinstance(args, Mapping) and any(isinstance(v, SqlExpr) for v in args.values()):
      query, args = sql_substitute_exprs(query, args)
    args = _sqlite_native_args(args)
    execute_start = get_time()
    try:
      res = super().execute(query, args)
    except sqlite3.Error as e:
      self.execute_time = get_time() - execute_start
      setattr(e, 'execute_time', self.execute_time)
      e.add_note(f'execute_time: {self.execute_time:.5f}s.')
      setattr(e, 'query', query)
      e.add_note(f'query: {query}')
      raise
    else:
      self.execute_time = get_time() - execute_start
      return res


  def executemany(self, query:str, it_args:Iterable[SqlParameters]) -> Self:
    '''
    For every item in `it_args`, repeatedly execute the parameterized DML SQL statement sql.
    Argument values are converted to sqlite-native values; see `sqlite_native_val`.

    Override executemany in order to set `query` on any resulting sqlite3.Error.
    '''
    it_args = map(_sqlite_native_args, it_args)
    execute_start = get_time()
    try:
      res = super().executemany(query, it_args)
    except sqlite3.Error as e:
      self.execute_time = get_time() - execute_start
      setattr(e, 'execute_time', self.execute_time)
      e.add_note(f'execute_time: {self.execute_time:.5f}s.')
      setattr(e, 'query', query)
      e.add_note(f'query: {query}')
      raise
    else:
      self.execute_time = get_time() - execute_start
      return res


  def executescript(self, sql_script:str) -> Self:
    '''
    Execute the SQL statements in sql_script.
    If the autocommit is LEGACY_TRANSACTION_CONTROL and there is a pending transaction,
    an implicit COMMIT statement is executed first.
    No other implicit transaction control is performed; any transaction control must be added to sql_script.

    Override executemany in order to set `query` on any resulting sqlite3.Error.
    '''
    execute_start = get_time()
    try:
      res = cast(Self, super().executescript(sql_script))
    except sqlite3.Error as e:
      self.execute_time = get_time() - execute_start
      setattr(e, 'execute_time', self.execute_time)
      e.add_note(f'execute_time: {self.execute_time:.5f}s.')
      setattr(e, 'query', sql_script)
      e.add_note(f'script: {sql_script}')
      raise
    else:
      self.execute_time = get_time() - execute_start
      return res


  def run(self, sql:str, *, _dbg:bool=False, **args:Any) -> Self:
    '''
    Execute a query with parameter values provided by keyword arguments.
    Argument values are converted to sqlite-native values by `execute`; see `sqlite_native_val`.
    `SqlExpr` argument values are substituted into the query as raw SQL.
    '''
    if _dbg:
      print(f'query: {sql.strip()}\n  args: {args}')
      if plan := self.execute(f'EXPLAIN QUERY PLAN {sql}', args).fetchone():
        print(f' plan: {tuple(plan)}')
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


  def count(self, table:str, *, where:str='', **args:Any) -> int:
    'Execute a SELECT COUNT() query, returning the number of rows.'
    where_clause = f' WHERE {where}' if where else ''
    for row in self.execute(f'SELECT COUNT() FROM {table}{where_clause}', args):
      return row[0] # type: ignore[no-any-return]
    raise Exception(f'No row returned from COUNT query: {table}{where_clause}')


  def exists(self, table:str, *, where:str, **args:Any) -> bool:
    'Execute a SELECT EXISTS (SELECT ...) query, returning True if at least one result matches the query.'
    return bool(self.execute(f'SELECT EXISTS (SELECT 1 FROM {table} WHERE {where})', args))


  @overload
  def insert(self, *, with_:str='', or_:str='FAIL', into:str, on_conflict:OnConflictTarget='', returning:tuple[str,...],
   **kwargs:Any) -> Row: ...

  @overload
  def insert(self, *, with_:str='', or_:str='FAIL', into:str, on_conflict:OnConflictTarget='', returning:str, **kwargs:Any) \
   -> Any: ...

  @overload
  def insert(self, *, with_:str='', or_:str='FAIL', into:str, on_conflict:OnConflictTarget='', returning:None=None,
   **kwargs:Any) -> None: ...

  def insert(self, *, with_:str='', or_:str='FAIL', into:str, on_conflict:OnConflictTarget='',
    returning:tuple[str,...]|str|None=None, _dbg:bool=False, **kwargs:Any) -> Row|Any|None:
    '''
    Execute an insert statement with the kwargs key/value pairs passed as named arguments.
    `SqlExpr` values are substituted into the statement as raw SQL instead of being bound as arguments.
    If `on_conflict` is specified, it must be a column name or a tuple of column names.
    In that case an ON CONFLICT clause is generated for those column names, that updates all other provided columns.
    If `returning` is a tuple, return a single row object; if it is a string, return a single column.
    '''
    exprs = frozendict((k, v) for k, v in kwargs.items() if isinstance(v, SqlExpr))
    stmt = insert_values_stmt(with_=with_, or_=or_, into=into, fields=tuple(kwargs.keys()), on_conflict=on_conflict,
      returning=returning, exprs=exprs)

    if exprs: kwargs = { k: v for k, v in kwargs.items() if k not in exprs }
    self.run(stmt, _dbg=_dbg, **kwargs)

    if isinstance(returning, tuple): return self.one()
    elif isinstance(returning, str): return self.one_col()
    else: return None


  @overload
  def insert_dict(self, *, with_:str='', or_:str='FAIL', into:str, fields:Iterable[str]|None=None,
   on_conflict:OnConflictTarget='', returning:tuple[str,...], args:dict[str, Any], defaults:dict[str,Any]=...) -> Row: ...

  @overload
  def insert_dict(self, *, with_:str='', or_:str='FAIL', into:str, fields:Iterable[str]|None=None,
   on_conflict:OnConflictTarget='', returning:str, args:dict[str,Any], defaults:dict[str,Any]=...) -> Any: ...

  @overload
  def insert_dict(self, *, with_:str='', or_:str='FAIL', into:str, fields:Iterable[str]|None=None,
   on_conflict:OnConflictTarget='', returning:None=None, args:dict[str,Any], defaults:dict[str,Any]=...) -> None: ...

  def insert_dict(self, *, with_:str='', or_:str='FAIL', into:str, fields:Iterable[str]|None=None,
   on_conflict:OnConflictTarget='', returning:tuple[str,...]|str|None=None, args:dict[str,Any], defaults:dict[str,Any]={}
   ) -> Any:
    '''
    Execute an insert of the dictionary `args`, synthesized from `into` (the table name) and `fields`.
    Values are pulled in by name first from the `args` dictionary, then from `defaults`;
    a KeyError is raised if one of the fields is not provided in either of these sources.
    `SqlExpr` values are substituted into the statement as raw SQL instead of being bound as arguments.
    If `returning` is a tuple, return a single row; if it is a string, return a single field value.
    '''
    fields = tuple(args.keys()) if fields is None else tuple(fields)

    def arg_for(f:str) -> Any:
      try: return args[f]
      except KeyError: pass
      return defaults[f]

    values = {f: arg_for(f) for f in fields}
    exprs = frozendict((f, v) for f, v in values.items() if isinstance(v, SqlExpr))
    if exprs: values = {f: v for f, v in values.items() if f not in exprs}

    stmt = insert_values_stmt(with_=with_, or_=or_, into=into, fields=fields, on_conflict=on_conflict, returning=returning,
      exprs=exprs)

    self.execute(stmt, values)

    if isinstance(returning, tuple): return self.one()
    elif isinstance(returning, str): return self.one_col()
    else: return None


  def insert_seq(self, *, with_:str='', or_:str='FAIL', into:str, fields:Iterable[str], seq:Sequence[Any]) -> None:
    '''
    Execute an insert of the sequence `args`, synthesized from `into` (the table name), and `fields`.
    `SqlExpr` values are substituted into the statement as raw SQL instead of being bound as arguments.
    '''
    fields = tuple(fields)
    values = dict(zip(fields, seq, strict=True))
    exprs = frozendict((f, v) for f, v in values.items() if isinstance(v, SqlExpr))
    if exprs: values = {f: v for f, v in values.items() if f not in exprs}
    stmt = insert_values_stmt(with_=with_, or_=or_, into=into, fields=fields, exprs=exprs)
    self.execute(stmt, values)


  def count_all_tables(self, *, schema:str='main', omit_empty:bool=False) -> list[tuple[str, int]]:
    'Return an iterable of (table, count) pairs.'
    schema_q = sql_quote_entity(schema)
    table_names = list(self.execute(f"SELECT name FROM {schema_q}.sqlite_schema WHERE type = 'table' ORDER BY name").col())
    pairs = []
    for name in table_names:
      count = self.count(f'{schema_q}.{name}')
      if omit_empty and count == 0: continue
      pairs.append((name, count))
    return pairs


  def update(self, table:str, *, with_:str='', or_:str='FAIL', by:str|tuple[str,...], _dbg:bool=False, **kwargs:Any) -> None:
    '''
    Execute an UPDATE statement.
    `SqlExpr` values are substituted into the statement as raw SQL instead of being bound as arguments;
    they are not permitted as `by` field values.
    TODO: support returning clause.
    '''
    if isinstance(by, str): by = (by,)
    if not isinstance(by, tuple): raise TypeError('`by` argument must be a string or tuple of strings.')
    if not by: raise ValueError('`by` argument must not be empty for safety.')
    for k in by:
      if isinstance(kwargs.get(k), SqlExpr): raise ValueError(f'`by` field value cannot be a SqlExpr: {k!r}')
    where = ' AND '.join(f'{sql_quote_entity(k)} = :{k}' for k in by)
    fields = tuple(k for k in kwargs if k not in by)
    exprs = frozendict((k, v) for k, v in kwargs.items() if k not in by and isinstance(v, SqlExpr))
    stmt = update_stmt(with_=with_, or_=or_, table=table, fields=fields, where=where, exprs=exprs)
    if exprs: kwargs = { k: v for k, v in kwargs.items() if k not in exprs }
    self.run(stmt, _dbg=_dbg, **kwargs)


  def user_version(self, namespace:str='main') -> int:
    'Return the integer value stored in the user_version pragma.'
    if not namespace.isidentifier(): raise ValueError(f'Invalid namespace: {namespace}')
    user_version = self.run(f'PRAGMA {namespace}.user_version').one_col()
    assert isinstance(user_version, int), user_version
    return user_version


  def set_user_version(self, namespace:str, version:int) -> None:
    'Set the integer value stored in the user_version pragma.'
    if not namespace.isidentifier(): raise ValueError(f'Invalid namespace: {namespace}')
    assert isinstance(version, int), version
    self.run(f'PRAGMA {namespace}.user_version = {version}')
