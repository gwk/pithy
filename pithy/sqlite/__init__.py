# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from sqlite3 import Row
from typing import Any, Dict, Iterable, Iterator, List, NamedTuple, Optional, Sequence, Tuple, Type, cast

from ..json import render_json
from .util import default_to_json, py_to_sql_types_tuple


class SqliteError(Exception):

  @property
  def failed_unique_constraint(self) -> Optional[str]:
    'Return the failed uniqueness constraint if that was the cause of the error or else None.'
    cause = self.__cause__
    if cause is None: return None
    msg = cause.args[0]
    suffix = msg.removeprefix('UNIQUE constraint failed: ')
    return suffix if suffix != msg else None


class Cursor(sqlite3.Cursor):

  def execute(self, query:str, args:Iterable=()) -> 'Cursor':
    try: return cast('Cursor', super().execute(query, args))
    except sqlite3.Error as e:
      raise SqliteError(f'SQLite error; query: {query!r}') from e


  def run(self, *sql:str, **args:Any) -> 'Cursor':
    '''
    Execute a query, joining multiple pieces of `sql` into a single query string, with values provided by keyword arguments.
    Argument values whose types are not sqlite-compatible are automatically converted to Json.
    '''
    query = ' '.join(sql)
    for k, v in args.items(): # Convert non-native values to Json.
      if not isinstance(v, py_to_sql_types_tuple):
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


  def insert(self, *, with_='', or_='FAIL', into:str, fields:Optional[Iterable[str]]=None, sql:str, args:Any=()) -> None:
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


  def insert_dict(self, *, with_='', or_='FAIL', into:str, fields:Optional[Iterable[str]]=None, args:Dict[str, Any],
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
    values = [default_to_json(arg_for(f)) for f in fields or args.keys()]
    self.insert(with_=with_, or_=or_, into=into, fields=fields, sql=f'VALUES ({placeholders})', args=values)


  def insert_seq(self, *, with_='', or_='FAIL', into:str, fields:Optional[Iterable[str]]=None, seq:Sequence[Any]) -> None:
    '''
    Execute an insert statement inserting the sequence `args`, synthesized from `into` (the table name), and `fields`.
    '''
    placeholders = ','.join('?' for _ in seq)
    values = [default_to_json(v) for v in seq]
    self.insert(with_=with_, or_=or_, into=into, fields=fields, sql=f'VALUES ({placeholders})', args=values)


class Connection(sqlite3.Connection):

  def __init__(self, path:str, timeout:float=5.0, detect_types:int=0, isolation_level:Optional[str]=None,
   check_same_thread:bool=True, cached_statements:int=100, uri:bool=False) -> None:

    super().__init__(path, timeout=timeout, detect_types=detect_types, isolation_level=isolation_level,
      check_same_thread=check_same_thread, cached_statements=cached_statements, uri=uri)

    self.row_factory = Row # Default for convenience.


  def cursor(self, factory:Optional[type]=None) -> Cursor:
    if factory is None:
      factory = Cursor
    assert issubclass(factory, Cursor)
    return cast(Cursor, super().cursor(factory))


  def run(self, *sql:str, **args:Any) -> Cursor:
    return self.cursor().run(*sql, **args)


  def contains(self, table:str, *where:str, **args:Any) -> bool:
    return self.cursor().contains(table, *where, **args)


  def insert(self, *, with_='', or_='FAIL', into:str, fields:Optional[Iterable[str]]=None, sql:str, args:Any=()) -> None:
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


  def insert_dict(self, *, with_='', or_='FAIL', into:str, fields:Optional[Iterable[str]]=None, args:Dict[str, Any],
   defaults:Dict[str, Any]={}) -> None:
    '''
    Execute an insert statement inserting the dictionary `args`, synthesized from `into` (the table name) and `fields`.
    Values are pulled in by name first from the `args` dictionary, then from `defaults`;
    a KeyError is raised if one of the fields is not provided in either of these sources.
    '''
    self.cursor().insert_dict(with_=with_, or_=or_, into=into, fields=fields, args=args, defaults=defaults)


  def insert_seq(self, *, with_='', or_='FAIL', into:str, fields:Optional[Iterable[str]]=None, seq:Sequence[Any]) -> None:
    '''
    Execute an insert statement inserting the sequence `args`, synthesized from `into` (the table name), and `fields`.
    '''
    self.cursor().insert_seq(with_=with_, or_=or_, into=into, fields=fields, seq=seq)
