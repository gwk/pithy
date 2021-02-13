# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from typing import Any, Dict, Iterable, Iterator, List, NamedTuple, Optional, Sequence, Tuple, Type, cast

from ..json import render_json
from .util import _default_to_json, py_to_sql_types_tuple


class SqliteError(Exception): pass


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
    args = [_default_to_json(v) for v in kwargs.values()]
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
    values = [_default_to_json(arg_for(f)) for f in fields or args.keys()]
    self.insert(with_=with_, or_=or_, into=into, fields=fields, sql=f'VALUES ({placeholders})', args=values)


  def insert_seq(self, *, with_='', or_='FAIL', into:str, fields:Optional[Iterable[str]]=None, seq:Sequence[Any]) -> None:
    '''
    Execute an insert statement inserting the sequence `args`, synthesized from `into` (the table name), and `fields`.
    '''
    placeholders = ','.join('?' for _ in seq)
    values = [_default_to_json(v) for v in seq]
    self.insert(with_=with_, or_=or_, into=into, fields=fields, sql=f'VALUES ({placeholders})', args=values)


  def select(self, *sql:str, **args:Any) -> 'Cursor':
    'Execute a SELECT query.'
    return self.run('SELECT', *sql, **args)


  def select_opt(self, *sql:str, **args:Any) -> Optional[sqlite3.Row]:
    'Execute a SELECT query, returning a single row or None.'
    return self.run('SELECT', *sql, **args).fetchone() # type: ignore


  def select_col(self, *sql:str, **args:Any) -> Iterator[Any]:
    'Execute a SELECT query, returning column 0 of each result row.'
    for row in self.run('SELECT', *sql, **args):
      assert len(row) == 1
      yield row[0]


  def select_one_col(self, *sql:str, **args:Any) -> Any:
    row = self.run('SELECT', *sql, **args).fetchone()
    if row is None: raise ValueError(None)
    return row[0]


  def contains(self, table:str, *where:str, **args:Any) -> bool:
    'Execute a SELECT query, returning True if the `where` SQL clause results in at least one row.`'
    for row in self.run('SELECT 1 FROM', table, 'WHERE', *where, 'LIMIT 1', **args):
      return True
    return False


  def update(self, table:str, *, cols:Iterable[str], where:str, **args:Any) -> None:
    bindings = [f'{col} = :{col}' for col in cols]
    bindings_clause = ', '.join(bindings)
    self.run('UPDATE', table, 'SET', bindings_clause, 'WHERE', where, **args)


class Connection(sqlite3.Connection):

  def __init__(self, path:str, uri:bool=False) -> None:
    super().__init__(path, uri=uri)
    self.row_factory = sqlite3.Row # default for convenience.
    #self.stmt_cache = {}

  def cursor(self, factory:Optional[type]=None) -> Cursor:
    if factory is None:
      factory = Cursor
    assert issubclass(factory, Cursor)
    return cast(Cursor, super().cursor(factory))

  def run(self, *sql:str, **args:Any) -> Cursor:
    return self.cursor().run(*sql, **args)


  def insert_row(self, *, with_='', or_='FAIL', into:str, **kwargs:Any) -> None:
    return self.cursor().insert_row(with_=with_, or_=or_, into=into, **kwargs)

  def insert_dict(self, *, with_='', or_='FAIL', into:str, fields:Optional[Iterable[str]]=None, args:Dict[str, Any],
   defaults:Dict[str, Any]={}) -> None:
    return self.cursor().insert_dict(with_=with_, or_=or_, into=into, fields=fields, args=args, defaults=defaults)

  def insert_seq(self, *, with_='', or_='FAIL', into:str, fields:Optional[Iterable[str]]=None, seq:Sequence[Any]) -> None:
    return self.cursor().insert_seq(with_=with_, or_=or_, into=into, fields=fields, seq=seq)


  def select(self, *sql:str, **args:Any) -> Cursor:
    return self.cursor().select(*sql, **args)

  def select_opt(self, *sql:str, **args:Any) -> Optional[sqlite3.Row]:
    return self.cursor().select_opt(*sql, **args)

  def select_col(self, *sql:str, **args:Any) -> Iterator[Any]:
    return self.cursor().select_col(*sql, **args)

  def select_one_col(self, *sql:str, **args:Any) -> Any:
    return self.cursor().select_one_col(*sql, **args)

  def contains(self, table:str, *where:str, **args:Any) -> bool:
    return self.cursor().contains(table, *where, **args)


  def update(self, table:str, *, cols:Iterable[str], where:str, **args:Any) -> None:
    return self.cursor().update(table, cols=cols, where=where, **args)
