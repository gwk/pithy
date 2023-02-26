# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from typing import Any, cast, Dict, Iterable, Iterator, Mapping, Optional, Protocol, Self, Sequence, Tuple, TypeAlias, TypeVar
from urllib.parse import quote as url_quote

from ..ansi import RST_TXT, TXT_B, TXT_C, TXT_D, TXT_G, TXT_M, TXT_R, TXT_Y
from ..json import render_json
from .util import default_to_json, sql_quote_entity, types_natively_converted_by_sqlite


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


class SqliteError(Exception):

  @classmethod
  def from_error(self, e:sqlite3.Error, query:str) -> 'SqliteError':
    orig_msg = e.args[0]
    msg = f'{orig_msg}\n  query: {query!r}'
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


  def run(self, *sql:str, dbg=False, **args:Any) -> Self:
    '''
    Execute a query, joining multiple pieces of `sql` into a single query string, with values provided by keyword arguments.
    Argument values whose types are not sqlite-compatible are automatically converted to Json.
    '''
    query = ' '.join(sql).strip()
    for k, v in args.items(): # Convert non-native values to Json.
      if not isinstance(v, types_natively_converted_by_sqlite): # Note: this is a conditional inlining of `default_to_json`.
        args[k] = render_json(v, indent=None)
    if dbg: print(f'query: {query}\n  args: {args}')
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
    where_clause = ('WHERE', *where) if where else ()
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


  def count_all_tables(self, schema:str='main', omit_empty=False) -> list[tuple[str, int]]:
    'Return an iterable of (table, count) pairs.'
    schema_q = sql_quote_entity(schema)
    table_names = list(self.run(f"SELECT name FROM {schema_q}.sqlite_schema WHERE type = 'table' ORDER BY name").col())
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


  def backup_and_print_progress(self, target:sqlite3.Connection|str|None=None, pages=-1, name='main', sleep=0.250) -> None:
    '''
    Backup this database to the target database, printing progress to stdout.
    '''
    if target is None: target = self.path + '.backup'

    close = False
    if isinstance(target, str):
      target = sqlite3.connect(target)
      close = True

    def progress(_status:int, remaining:int, total:int):
      frac = (total - remaining) / total
      print(f'Backup {name!r}: {frac:0.1%}…', end='\r')

    print(f'Backup {name!r}…')
    try: self.backup(target, pages=pages, progress=progress, name=name, sleep=sleep)
    finally:
      if close: target.close()
    print(f'Backup {name!r} complete.')
