# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from contextlib import AbstractContextManager
from sqlite3 import (DatabaseError, DataError, IntegrityError, InterfaceError, InternalError, NotSupportedError,
  OperationalError, ProgrammingError)
from typing import (Any, Callable, cast, Iterable, Iterator, Literal, Mapping, overload, Protocol, Self, Sequence, TypeAlias,
  TypeVar)
from urllib.parse import quote as url_quote

from ..ansi import RST_TXT, TXT_B, TXT_C, TXT_D, TXT_G, TXT_M, TXT_R, TXT_Y
from ..typing import OptBaseExc, OptTraceback, OptTypeBaseExc
from .util import default_to_json, insert_values_stmt, sql_quote_entity, update_stmt, update_to_json


SqliteError:TypeAlias = sqlite3.Error
SqliteWarning:TypeAlias = sqlite3.Warning

# Silence linter by referencing imported names.
_ = (DatabaseError, DataError, IntegrityError, InterfaceError, InternalError, NotSupportedError, OperationalError,
  ProgrammingError)


_T_co = TypeVar('_T_co', covariant=True)

class _SupportsLenAndGetItemByInt(Protocol[_T_co]):
  def __len__(self) -> int: ...
  def __getitem__(self, __k:int) -> _T_co: ...

_ReadableBuffer:TypeAlias = bytes | bytearray | memoryview # | array.array[Any] | mmap.mmap | ctypes._CData | pickle.PickleBuffer

_SqliteData:TypeAlias = str | _ReadableBuffer | int | float | None

_AdaptedInputData:TypeAlias = _SqliteData | Any
#^ Data that is passed through adapters can be of any type accepted by an adapter.

_SqlParameters: TypeAlias = _SupportsLenAndGetItemByInt[_AdaptedInputData] | Mapping[str, _AdaptedInputData]
#^ The Mapping must really be a dict, but making it invariant is too annoying.

sqlite_version = sqlite3.sqlite_version
sqlite_threadsafe_dbapi_id = sqlite3.threadsafety

sqlite_threadsafe_dbapi_id_descs = [
  '0 - single-thread (threads may not share the module).',
  '1 - multi-thread (threads may share the module, but not connections).',
  '2 - invalid.',
  '3 - serialized (threads may share the module and connections).',
]

sqlite_threadsafe_desc = sqlite_threadsafe_dbapi_id_descs[sqlite_threadsafe_dbapi_id]


BackupProgressFn = Callable[[int,int,int],object]


class Row(sqlite3.Row):
  'A row of a query result. Subclasses sqlite3.Row to add property access.'

  def __getattr__(self, key:str) -> Any:
    try: return self[key]
    except IndexError as e: raise AttributeError(key) from e

  def get(self, key:str, default:Any=None) -> Any:
    try: return self[key]
    except IndexError: return default

  def items(self) -> Iterator[tuple[str, Any]]:
    'Return an iterator of (key, value) pairs.'
    for key in self.keys():
      yield key, self[key]

  def qdi(self) -> str:
    '"quick describe inline". Return a string describing the query result.'
    parts = []
    for key, val in self.items():
      color = _row_qdi_colors.get(type(val), TXT_R)
      parts.append(f'{TXT_D}{key}:{color}{val!r}{RST_TXT}')
    return '  '.join(parts)


_row_qdi_colors = {
  bool: TXT_G,
  bytes: TXT_M,
  float: TXT_B,
  int: TXT_C,
  str: TXT_Y,
  type(None): TXT_R,
}


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


  def execute(self, query:str, args:_SqlParameters=()) -> Self:
    '''
    Execute a single SQL statement, optionally binding Python values using placeholders.

    Override execute in order to set `query` on any resulting sqlite3.Error.
    '''
    try: return super().execute(query, args)
    except sqlite3.Error as e:
      setattr(e, 'query', query)
      raise


  def executemany(self, query:str, it_args:Iterable[_SqlParameters]) -> Self:
    '''
    For every item in `it_args`, repeatedly execute the parameterized DML SQL statement sql.

    Override executemany in order to set `query` on any resulting sqlite3.Error.
    '''
    try: return super().executemany(query, it_args)
    except sqlite3.Error as e:
      setattr(e, 'query', query)
      raise


  def executescript(self, sql_script:str) -> Self:
    '''
    Execute the SQL statements in sql_script. If the autocommit is LEGACY_TRANSACTION_CONTROL and there is a pending transaction, an implicit COMMIT statement is executed first. No other implicit transaction control is performed; any transaction control must be added to sql_script.

    Override executemany in order to set `query` on any resulting sqlite3.Error.
    '''
    try: return cast(Self, super().executescript(sql_script))
    except sqlite3.Error as e:
      setattr(e, 'query', sql_script)
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


  def opt_col(self) -> Any:
    if row := self.fetchone():
      assert len(row) == 1
      return row[0]
    else:
      return None


  def one_col(self) -> Any:
    row = self.fetchone()
    if row is None: raise ValueError(None)
    assert len(row) == 1
    return row[0]


  def contains(self, table:str, *, where:str, **args:Any) -> bool:
    'Execute a SELECT query, returning True if the `where` SQL clause results in at least one row.`'

    for row in self.execute(f'SELECT 1 FROM {table} WHERE {where} LIMIT 1', args):
      return True
    return False


  def count(self, table:str, *, where='', **args:Any) -> int:
    'Execute a SELECT COUNT() query, returning the number of rows.'
    where_clause = f' WHERE {where}' if where else ''
    for row in self.execute(f'SELECT COUNT() FROM {table}{where_clause}', args):
      return row[0] # type: ignore[no-any-return]
    return 0


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
    if not by: raise ValueError('`by` argument must not be empty for safety.')
    where = ' AND '.join(f'{sql_quote_entity(k)} = :{k}' for k in by)
    fields = tuple(k for k in kwargs if k not in by)
    stmt = update_stmt(with_=with_, or_=or_, table=table, named=True, fields=fields, where=where)
    self.run(stmt, _dbg=_dbg, **kwargs)



class Conn(sqlite3.Connection):

  def __init__(self, path:str, timeout:float=5.0, detect_types:int=0, isolation_level:str|None=None,
   check_same_thread:bool=True, cached_statements:int=100, uri:bool=False, *, mode='') -> None:

    self.path = path
    self.mode = mode
    if mode:
      if uri: raise ValueError('Cannot specify both `uri` and `mode`')
      path = sqlite_file_uri(path, mode=mode)
      uri = True

    if isolation_level not in (None, 'DEFERRED', 'IMMEDIATE', 'EXCLUSIVE'): raise ValueError(isolation_level)

    super().__init__(path, timeout=timeout, detect_types=detect_types, isolation_level=isolation_level,
      check_same_thread=check_same_thread, cached_statements=cached_statements, uri=uri)

    self.row_factory = Row # Default for convenience.


  def __enter__(self) -> Self:
    '''
    On context manager enter, Conn does nothing.
    '''
    return self


  def __exit__(self, exc_type:OptTypeBaseExc, exc_value:OptBaseExc, traceback:OptTraceback) -> Literal[False]:
    '''
    On context manager exit, Conn closes itself.
    This differs from the behavior of sqlite3.Connection, which performs commit/rollback on exit, but does not close.
    '''
    self.close()
    return False # Propagate any exceptions. The return of False instead of None is required to match that super().


  def attach(self, path:str, *, name:str, mode='') -> None:
    '''
    Attach another database to this one using the URI syntax with the specified mode.
    `mode` must be one of '' (default, omitted in the SQL statement), 'ro', 'rw', 'rwc', or 'memory'.
    '''
    uri = sqlite_file_uri(path, mode=mode)
    super().execute(f'ATTACH DATABASE {sql_quote_entity(uri)} AS {sql_quote_entity(name)}')


  def validate(self, query:str) -> None:
    '''
    Validate a query string by calling the undocumented sqlite3 API to compile a statement.
    '''
    super().__call__(query)


  def cursor(self, factory:type[Cursor]|None=None) -> Cursor: # type: ignore[override]
    if factory is None: factory = Cursor
    assert issubclass(factory, Cursor)
    return super().cursor(factory)


  def execute(self, query:str, args:_SqlParameters=()) -> Cursor:
    '''
    Execute a single SQL statement, optionally binding Python values using placeholders.

    Override execute in order to set `query` on any resulting sqlite3.Error.
    '''
    with self.cursor() as c:
      return c.execute(query, args)


  def executemany(self, query:str, it_args:Iterable[_SqlParameters]) -> Cursor:
    '''
    For every item in `it_args`, repeatedly execute the parameterized DML SQL statement sql.

    Override executemany in order to set `query` on any resulting sqlite3.Error.
    '''
    with self.cursor() as c:
      return c.executemany(query, it_args)


  def executescript(self, sql_script:str) -> Cursor:
    '''
    Execute the SQL statements in sql_script. If the autocommit is LEGACY_TRANSACTION_CONTROL and there is a pending transaction, an implicit COMMIT statement is executed first. No other implicit transaction control is performed; any transaction control must be added to sql_script.

    Override executemany in order to set `query` on any resulting sqlite3.Error.
    '''
    with self.cursor() as c:
      return c.executescript(sql_script)


  def backup(self, target:sqlite3.Connection|str|None=None, *, pages:int=-1, progress:BackupProgressFn|bool|None=None,
   name='main', sleep=0.250) -> None:
    '''
    Backup this database to the target database, optionally printing progress to stdout.
    This is an override of sqlite3.Connection.backup, adding the `progress` argument for convenience.
    '''
    if target is None: target = self.path + '.backup'

    should_close_target = False
    if isinstance(target, str):
      target = sqlite3.connect(target)
      should_close_target = True

    path = getattr(target, 'path', '')

    progress_fn:BackupProgressFn|None = None
    if progress:
      if callable(progress):
        progress_fn = progress
      else:
        def progress_fn(_status:int, remaining:int, total:int):
          frac = (total - remaining) / total
          print(f'Backup {path}:{name}: {frac:0.1%}…', end='\r')

      print(f'Backup {path}:{name}…', end='\r')

    try:
      super().backup(target, pages=pages, progress=progress_fn, name=name, sleep=sleep)
    finally:
      if should_close_target: target.close()

    if progress: print(f'Backup {path}:{name} complete.')


  def run(self, sql:str, *, _dbg=False, **args:Any) -> Cursor:
    '''
    Execute a query with parameter values provided by keyword arguments.
    Argument values whose types are not sqlite-compatible are automatically converted to JSON.
    '''
    return self.cursor().run(sql, _dbg=_dbg, **args)


def sqlite_file_uri(path:str, *, mode:str='') -> str:
  '''
  Format an SQLite file URI.
  Mode must be one of '' (default, omitted), 'ro', 'rw', 'rwc', or 'memory'.
  TODO: suppport the other documented attributes: https://www.sqlite.org/uri.html.

  '''
  valid_modes = ('', 'ro', 'rw', 'rwc', 'memory')
  if mode not in valid_modes: raise ValueError(mode)
  uri = f'file:{url_quote(path)}'
  if mode:
    uri += f'?mode={mode}'
  return uri
