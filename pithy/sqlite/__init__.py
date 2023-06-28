# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from typing import Any, Callable, cast, Iterable, Iterator, Mapping, overload, Protocol, Self, Sequence, TypeAlias, TypeVar
from urllib.parse import quote as url_quote

from ..ansi import RST_TXT, TXT_B, TXT_C, TXT_D, TXT_G, TXT_M, TXT_R, TXT_Y
from ..json import render_json
from .util import default_to_json, insert_values_stmt, sql_quote_entity, types_natively_converted_by_sqlite


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


class SqliteError(Exception):

  @classmethod
  def from_error(self, e:sqlite3.Error, query:str) -> 'SqliteError':
    orig_msg = e.args[0]
    msg = f'{orig_msg}\n  Query: {query!r}'
    prefix = e.args[0].partition(':')[0]
    match prefix:
      case 'UNIQUE constraint failed': return SqliteUniqueConstraintError(msg)
      case 'FOREIGN KEY constraint failed': return SqliteForeignKeyConstraintError(msg)
      case 'NOT NULL constraint failed': return SqliteNotNullConstraintError(msg)
      case _: return SqliteError(msg)


class SqliteIntegrityError(SqliteError): pass

class SqliteForeignKeyConstraintError(SqliteIntegrityError): pass

class SqliteNotNullConstraintError(SqliteIntegrityError): pass

class SqliteUniqueConstraintError(SqliteIntegrityError): pass



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


class Cursor(sqlite3.Cursor):

  def execute(self, query:str, args:_SqlParameters=()) -> Self:
    '''
    Override execute in order to raise an SqliteError with the complete query string.
    '''
    try: return super().execute(query, args)
    except sqlite3.Error as e: raise SqliteError.from_error(e, query) from e


  def executemany(self, query:str, it_args:Iterable[_SqlParameters]) -> Self:
    '''
    Override executemany in order to raise an SqliteError with the complete query string.
    '''
    try: return super().executemany(query, it_args)
    except sqlite3.Error as e: raise SqliteError.from_error(e, query) from e


  def executescript(self, sql_script:str) -> Self:
    '''
    Override executescript in order to raise an SqliteError with the complete query string.
    '''
    try: return cast(Self, super().executescript(sql_script))
    except sqlite3.Error as e: raise SqliteError.from_error(e, sql_script) from e


  def run(self, sql:str, *, _dbg=False, **args:Any) -> Self:
    '''
    Execute a query with parameter values provided by keyword arguments.
    Argument values whose types are not sqlite-compatible are automatically converted to Json.
    '''
    for k, v in args.items(): # Convert non-native values to Json.
      if not isinstance(v, types_natively_converted_by_sqlite): # Note: this is a conditional inlining of `default_to_json`.
        args[k] = render_json(v, indent=None)
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
    'Execute a SELECT COUNT(1) query, returning the number of rows.'
    where_clause = f' WHERE {where}' if where else ''
    for row in self.execute(f'SELECT COUNT(1) FROM {table}{where_clause}', args):
      return row[0] # type: ignore[no-any-return]
    return 0


  @overload
  def insert(self, *, with_='', or_='FAIL', into:str, as_json=False, returning:tuple[str,...], **kwargs:Any) -> Row: ...

  @overload
  def insert(self, *, with_='', or_='FAIL', into:str, as_json=False, returning:str, **kwargs:Any) -> Any: ...

  @overload
  def insert(self, *, with_='', or_='FAIL', into:str, as_json=False, returning:None=None, **kwargs:Any) -> None: ...

  def insert(self, *, with_='', or_='FAIL', into:str, as_json=False, returning:tuple[str,...]|str|None=None, **kwargs:Any):
    '''
    Execute an insert statement with the kwargs key/value pairs passed as named arguments.
    If `returning` is a tuple, return a single row; if it is a string, return a single column.
    '''
    stmt = insert_values_stmt(with_=with_, or_=or_, into=into, named=True, fields=tuple(kwargs.keys()), returning=returning)
    if as_json and not all(isinstance(v, types_natively_converted_by_sqlite) for v in kwargs.values()):
      kwargs = {k: default_to_json(v) for k, v in kwargs.items()}

    self.execute(stmt, kwargs)

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


  def count_all_tables(self, schema:str='main', omit_empty=False) -> list[tuple[str, int]]:
    'Return an iterable of (table, count) pairs.'
    schema_q = sql_quote_entity(schema)
    table_names = list(self.execute(f"SELECT name FROM {schema_q}.sqlite_schema WHERE type = 'table' ORDER BY name").col())
    pairs = []
    for name in table_names:
      count = self.count(f'{schema_q}.{name}')
      if omit_empty and count == 0: continue
      pairs.append((name, count))
    return pairs



class Connection(sqlite3.Connection):

  def __init__(self, path:str, timeout:float=5.0, detect_types:int=0, isolation_level:str|None=None,
   check_same_thread:bool=True, cached_statements:int=100, uri:bool=False, readonly=False) -> None:

    self.path = path
    self.readonly = readonly
    if readonly:
      if uri: raise ValueError('Cannot use URI with readonly=True')
      path = f'file:{url_quote(path)}?mode=ro'
      uri = True

    super().__init__(path, timeout=timeout, detect_types=detect_types, isolation_level=isolation_level,
      check_same_thread=check_same_thread, cached_statements=cached_statements, uri=uri)

    self.row_factory = Row # Default for convenience.


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
    Override execute in order to raise an SqliteError with the complete query string.
    '''
    try: return cast(Cursor, super().execute(query, args))
    except sqlite3.Error as e: raise SqliteError.from_error(e, query) from e


  def executemany(self, query:str, it_args:Iterable[_SqlParameters]) -> Cursor:
    '''
    Override executemany in order to raise an SqliteError with the complete query string.
    '''
    try: return cast(Cursor, super().executemany(query, it_args))
    except sqlite3.Error as e: raise SqliteError.from_error(e, query) from e


  def executescript(self, sql_script:str) -> Cursor:
    '''
    Override executescript in order to raise an SqliteError with the complete query string,
    and to return pithy.sqlite.Cursor instead of sqlite3.Cursor.
    '''
    try: return self.cursor().executescript(sql_script)
    except sqlite3.Error as e: raise SqliteError.from_error(e, sql_script) from e


  def backup(self, target:sqlite3.Connection|str|None=None, *, pages:int=-1, progress:BackupProgressFn|bool|None=None,
   name='main', sleep=0.250) -> None:
    '''
    Backup this database to the target database, optionally printing progress to stdout.
    This is an override of sqlite3.Connection.backup, adding the `progress` argument for convenience.
    '''
    if target is None: target = self.path + '.backup'

    close = False
    if isinstance(target, str):
      target = sqlite3.connect(target)
      close = True

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
      if close: target.close()

    if progress: print(f'Backup {path}:{name} complete.')
