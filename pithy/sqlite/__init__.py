# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from typing import Any, Dict, Iterable, Iterator, Mapping, Optional, Protocol, Sequence, Tuple, TypeAlias, TypeVar, cast

from ..ansi import RST_TXT, TXT_B, TXT_C, TXT_D, TXT_G, TXT_M, TXT_R, TXT_Y
from ..json import render_json
from .util import default_to_json, py_to_sqlite_types_tuple


_T_co = TypeVar('_T_co', covariant=True)

class _SupportsLenAndGetItemByInt(Protocol[_T_co]):
  def __len__(self) -> int: ...
  def __getitem__(self, __k:int) -> _T_co: ...

_ReadableBuffer:TypeAlias = bytes | bytearray | memoryview # | array.array[Any] | mmap.mmap | ctypes._CData | pickle.PickleBuffer

_SqliteData:TypeAlias = str | _ReadableBuffer | int | float | None

_AdaptedInputData:TypeAlias = _SqliteData | Any # type: ignore[operator]
#^ Data that is passed through adapters can be of any type accepted by an adapter.

_SqlParameters: TypeAlias = _SupportsLenAndGetItemByInt[_AdaptedInputData] | Mapping[str, _AdaptedInputData]
#^ The Mapping must really be a dict, but making it invariant is too annoying.


class SqliteError(Exception):

  @property
  def failed_unique_constraint(self) -> Optional[str]:
    'Return the failed uniqueness constraint if that was the cause of the error or else None.'
    cause = self.__cause__
    if cause is None: return None
    msg:str = cause.args[0]
    suffix = msg.removeprefix('UNIQUE constraint failed: ')
    if suffix == msg: return None
    return suffix


class Row(sqlite3.Row):
  'A row of a query result. Subclasses sqlite3.Row to add property access.'

  def __getattr__(self, key:str) -> Any:
    try: return self[key]
    except IndexError as e: raise AttributeError(key) from e

  def items(self) -> Iterator[Tuple[str, Any]]:
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

  def execute(self, query:str, args:_SqlParameters=()) -> 'Cursor':
    '''
    Override execute so that we can raise an SqliteError with the complete query string.
    '''
    try: return super().execute(query, args)
    except sqlite3.Error as e:
      raise SqliteError(f'SQLite error: {e}\n  query: {query!r}') from e


  def executemany(self, query:str, it_args:Iterable[_SqlParameters]) -> 'Cursor':
    '''
    Override executemany so that we can raise an SqliteError with the complete query string.
    '''
    try: return super().executemany(query, it_args)
    except sqlite3.Error as e:
      raise SqliteError(f'SQLite error: {e}\n  query: {query!r}') from e


  def run(self, *sql:str, **args:Any) -> 'Cursor':
    '''
    Execute a query, joining multiple pieces of `sql` into a single query string, with values provided by keyword arguments.
    Argument values whose types are not sqlite-compatible are automatically converted to Json.
    '''
    query = ' '.join(sql)
    for k, v in args.items(): # Convert non-native values to Json.
      if not isinstance(v, py_to_sqlite_types_tuple):
        args[k] = render_json(v, indent=None)
    return self.execute(query, args)


  def opt(self) -> Optional[Row]:
    'Return a single, optional row.'
    return cast(Optional[Row], self.fetchone())


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


  def contains(self, table:str, *where:str, **args:Any) -> bool:
    'Execute a SELECT query, returning True if the `where` SQL clause results in at least one row.`'
    for row in self.run('SELECT 1 FROM', table, 'WHERE', *where, 'LIMIT 1', **args):
      return True
    return False


  def count(self, table:str, *where:str, **args:Any) -> int:
    'Execute a SELECT COUNT(1) query, returning the number of rows.'
    where_clause = ('WHERE', *where) if where else []
    for row in self.run('SELECT COUNT(1) FROM', table, *where_clause, **args):
      return row[0] # type: ignore[no-any-return]
    return 0


  def insert(self, *, with_='', or_='FAIL', into:str, fields:Iterable[str]|None=None, sql:str, args:Any=()) -> None:
    '''
    Execute an insert statement synthesized from `into` (the table name), `fields` (optional), and `sql`.
    This function is intended to be an intermediate helper for higher level insert functions.
    '''
    assert or_ in {'ABORT', 'FAIL', 'IGNORE', 'REPLACE', 'ROLLBACK'}
    if fields:
      fields_joined = ', '.join(fields)
      fields_clause = f' ({fields_joined})'
    else:
      fields_clause = ''
    with_space = ' ' if with_ else ''
    complete_sql = f'{with_}{with_space}INSERT OR {or_} INTO {into}{fields_clause} {sql}'
    # TODO: cache sql with (with_, or_, into, fields, sql) key.
    self.execute(complete_sql, args)


  def insert_row(self, *, with_='', or_='FAIL', into:str, **kwargs:Any) -> None:
    '''
    Execute an insert statement inserting the kwargs key/value pairs passed as named arguments.
    '''
    placeholders = ','.join(['?'] * len(kwargs))
    args = [default_to_json(v) for v in kwargs.values()]
    self.insert(with_=with_, or_=or_, into=into, fields=kwargs.keys(), sql=f'VALUES ({placeholders})', args=args)


  def insert_dict(self, *, with_='', or_='FAIL', into:str, fields:Iterable[str]|None=None, args:Dict[str, Any],
   defaults:Dict[str, Any]={}) -> None:
    '''
    Execute an insert statement inserting the dictionary `args`, synthesized from `into` (the table name) and `fields`.
    Values are pulled in by name first from the `args` dictionary, then from `defaults`;
    a KeyError is raised if one of the fields is not provided in either of these sources.
    '''
    def arg_for(f: str) -> Any:
      try: return args[f]
      except KeyError: pass
      return defaults[f]

    placeholders = ','.join('?' for _ in args)
    if fields is None: fields = args.keys()
    values = [default_to_json(arg_for(f)) for f in fields]
    self.insert(with_=with_, or_=or_, into=into, fields=fields, sql=f'VALUES ({placeholders})', args=values)


  def insert_seq(self, *, with_='', or_='FAIL', into:str, fields:Iterable[str]|None=None, seq:Sequence[Any]) -> None:
    '''
    Execute an insert statement inserting the sequence `args`, synthesized from `into` (the table name), and `fields`.
    '''
    placeholders = ','.join('?' for _ in seq)
    values = [default_to_json(v) for v in seq]
    self.insert(with_=with_, or_=or_, into=into, fields=fields, sql=f'VALUES ({placeholders})', args=values)


class Connection(sqlite3.Connection):

  def __init__(self, path:str, timeout:float=5.0, detect_types:int=0, isolation_level:str|None=None,
   check_same_thread:bool=True, cached_statements:int=100, uri:bool=False) -> None:

    self.path = path

    super().__init__(path, timeout=timeout, detect_types=detect_types, isolation_level=isolation_level,
      check_same_thread=check_same_thread, cached_statements=cached_statements, uri=uri)

    self.row_factory = Row # Default for convenience.


  def cursor(self, factory:type|None=None) -> Cursor: # type: ignore[override]
    if factory is None:
      factory = Cursor
    assert issubclass(factory, Cursor)
    return super().cursor(factory)


  def run(self, *sql:str, **args:Any) -> Cursor:
    return self.cursor().run(*sql, **args)


  def contains(self, table:str, *where:str, **args:Any) -> bool:
    return self.cursor().contains(table, *where, **args)


  def count(self, table:str, *where:str, **args:Any) -> int:
    return self.cursor().count(table, *where, **args)


  def insert(self, *, with_='', or_='FAIL', into:str, fields:Iterable[str]|None=None, sql:str, args:Any=()) -> None:
    '''
    Execute an insert statement synthesized from `into` (the table name), `fields` (optional), and `sql`.
    This function is intended to be an intermediate helper for higher level insert functions.
    '''
    self.cursor().insert(with_=with_, or_=or_, into=into, fields=fields, sql=sql, args=args)


  def insert_row(self, *, with_='', or_='FAIL', into:str, **kwargs:Any) -> None:
    '''
    Execute an insert statement inserting the kwargs key/value pairs passed as named arguments.
    '''
    self.cursor().insert_row(with_=with_, or_=or_, into=into, **kwargs)


  def insert_dict(self, *, with_='', or_='FAIL', into:str, fields:Iterable[str]|None=None, args:Dict[str, Any],
   defaults:Dict[str, Any]={}) -> None:
    '''
    Execute an insert statement inserting the dictionary `args`, synthesized from `into` (the table name) and `fields`.
    Values are pulled in by name first from the `args` dictionary, then from `defaults`;
    a KeyError is raised if one of the fields is not provided in either of these sources.
    '''
    self.cursor().insert_dict(with_=with_, or_=or_, into=into, fields=fields, args=args, defaults=defaults)


  def insert_seq(self, *, with_='', or_='FAIL', into:str, fields:Iterable[str]|None=None, seq:Sequence[Any]) -> None:
    '''
    Execute an insert statement inserting the sequence `args`, synthesized from `into` (the table name), and `fields`.
    '''
    self.cursor().insert_seq(with_=with_, or_=or_, into=into, fields=fields, seq=seq)
