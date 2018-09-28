# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import sqlite3
from typing import *
from .io import *
from .json import Json, render_json


class SqliteError(Exception): pass


class Cursor(sqlite3.Cursor):

  def execute(self, query: str, args:Iterable=()) -> 'Cursor':
    try: return cast('Cursor', super().execute(query, args))
    except sqlite3.Error as e:
      raise SqliteError(f'SQLite error; query: {query!r}') from e

  def run(self, *sql: str, **args: Any) -> 'Cursor':
    '''
    Execute a query, joining multiple pieces of `sql` into a single query string, with values provided by keyword arguments.
    Values whose types are not sqlite compatible are automatically converted to Json.
    '''
    query = ' '.join(sql)
    for k, v in args.items(): # Convert non-native values to Json.
      if not isinstance(v, py_to_sql_types_tuple):
        args[k] = render_json(v, indent=None)
    return self.execute(query, args)


  def insert(self, *, with_='', or_='FAIL', table: str, fields: Tuple[str, ...], sql: str, args: Any) -> None:
    '''
    Execute an insert statement synthesized from `table`, `fields`, and `sql`.
    '''
    assert or_ in {'ABORT', 'FAIL', 'IGNORE', 'REPLACE', 'ROLLBACK'}
    fields_str = ', '.join(fields)
    with_space = ' ' if with_ else ''
    sql = f'{with_}{with_space}INSERT OR {or_} INTO {table} ({fields_str}) {sql}'
    # TODO: cache sql with (with_, or_, table, fields, sql) key.
    self.execute(sql, args)


  def insert_seq(self, *, with_='', or_='FAIL', table: str, fields: Tuple[str, ...], args: Sequence[Any]) -> None:
    '''
    Execute an insert statement inserting the sequence `args`, synthesized from `table`, and `fields`.
    '''
    assert len(fields) == len(args)
    placeholders = ','.join('?' for _ in fields)
    self.insert(with_=with_, or_=or_, table=table, fields=fields, sql=f'VALUES ({placeholders})', args=args)


  def insert_dict(self, *, with_='', or_='FAIL', table:str, fields:Tuple[str, ...],
   args:Dict[str, Any], defaults:Dict[str, Any]={}, **overrides:Any) -> None:
    '''
    Execute an insert statement inserting the dictionary `args`, synthesized from `table`, `fields`.
    Values are pulled by name in order of preference from keyword argument overrides, the `args` dictionary, and `defaults`;
    a KeyError is raised if one of the fields is not provided in any of these sources.
    '''
    def arg_for(f: str) -> Any:
      try: return overrides[f]
      except KeyError: pass
      try: return args[f]
      except KeyError: pass
      return defaults[f]
    args_seq = [_default_to_json(arg_for(f)) for f in fields]
    self.insert_seq(with_=with_, or_=or_, table=table, fields=fields, args=args_seq)


  def select(self, *sql: str, **args: Any) -> Cursor:
    'Execute a SELECT query.'
    return self.run('SELECT', *sql, **args)

  def select_opt(self, *sql: str, **args: Any) -> Optional[List[Any]]:
    'Execute a SELECT query, returning a single row or None.'
    return self.run('SELECT', *sql, **args).fetchone() # type: ignore

  def select_col(self, *sql: str, **args: Any) -> Iterator[Any]:
    'Execute a SELECT query, returning column 0 of each result row.'
    for row in self.run('SELECT', *sql, **args):
      assert len(row) == 1
      yield row[0]

  def contains(self, table: str, *criteria: str, **args: Any) -> bool:
    'Execute a SELECT query, returning True if the `criteria` SQL result in a row.`'
    for row in self.run('SELECT 1 FROM', table, 'WHERE', *criteria, 'LIMIT 1', **args):
      return True
    return False


class Connection(sqlite3.Connection):

  def __init__(self, path: str, uri:bool=False) -> None:
    super().__init__(path, uri=uri) # type: ignore
    self.row_factory = sqlite3.Row # default for convenience.
    #self.stmt_cache = {}

  def cursor(self, factory:Optional[type]=None) -> Cursor:
    if factory is None:
      factory = Cursor
    assert issubclass(factory, Cursor)
    return cast(Cursor, super().cursor(factory))

  def run(self, *sql: str, **args: Any) -> Cursor:
    return self.cursor().run(*sql, **args)

  def insert(self, *, with_='', or_='FAIL', table: str, fields: Tuple[str, ...], sql: str, args: Any) -> None:
    return self.cursor().insert(with_=with_, or_=or_, table=table, fields=fields, sql=sql, args=args)

  def insert_seq(self, *, with_='', or_='FAIL', table: str, fields: Tuple[str, ...], args: Sequence[Any]) -> None:
    return self.cursor().insert_seq(with_=with_, or_=or_, table=table, fields=fields, args=args)

  def insert_dict(self, *, with_='', or_='FAIL', table:str, fields:Tuple[str, ...],
   args:Dict[str, Any], defaults:Dict[str, Any]={}, **overrides:Any) -> None:
    return self.cursor().insert_dict(with_=with_, or_=or_, table=table, fields=fields, args=args, defaults=defaults, **overrides)

  def select(self, *sql: str, **args: Any) -> Cursor:
    return self.select(*sql, **args)

  def select_opt(self, *sql: str, **args: Any) -> Optional[List[Any]]:
    return self.select_opt(*sql, **args)

  def select_col(self, *sql: str, **args: Any) -> Iterator[Any]:
    return self.select_col(*sql, **args)


  def contains(self, table: str, *criteria: str, **args: Any) -> bool:
    return self.contains(table, *criteria, **args)



def sql_col_names(dataclass: type) -> str:
  '''
  Given a dataclass or NamedTuple subclass, return a string of comma-separated field names.
  '''
  return ', '.join(fields_of(dataclass))


def sql_col_placeholders(dataclass: type) -> str:
  '''
  Given a dataclass or NamedTuple subclass, return a string of comma-separated SQL named placeholders.
  '''
  return ', '.join(f':{n}' for n in fields_of(dataclass))


def sql_col_decls(class_: Type[NamedTuple], primary: str) -> str:
  '''
  Given a dataclass or NamedTuple subclass, yield a sequence of SQL column declarations for use in a CREATE TABLE statement.
  '''
  decls = []
  for n, static_type in class_._field_types.items():
    # Currently supports primitive types and their optionals, and Json.
    try: sql_type = py_to_sql_types[static_type]
    except KeyError:
      try: unwrapped_type = _wrapped_type_for_optional(static_type)
      except TypeError: sql_type = 'TEXT'
      else: sql_type = py_to_sql_types.get(unwrapped_type, 'TEXT')
    suffix = f' PRIMARY KEY' if n == primary else ''
    decls.append(f'{n} {sql_type}{suffix}')
  return ', '.join(decls)


def _wrapped_type_for_optional(static_type: type) -> type:
  # Optionals are really unions, which are a pain to work with at runtime.
  try: meta_class_name = static_type.__class__.__name__
  except AttributeError as e: raise TypeError(static_type) from e
  if meta_class_name != '_Union': raise TypeError(static_type)
  members = static_type.__args__ # type: ignore
  if len(members) != 2 or NoneType not in members: raise TypeError(static_type)
  return [m for m in members if m is not NoneType][0] # type: ignore


def _default_to_json(obj: Any) -> Any:
  if isinstance(obj, py_to_sql_types_tuple): return obj
  return render_json(obj)


def fields_of(class_: type) -> Tuple[str, ...]:
  if issubclass(class_, NamedTuple): return class_._fields # type: ignore
  # TODO: support dataclasses.
  raise TypeError(class_)


NoneType = type(None)

py_to_sql_types: Dict[type, str] = {
  int : 'INTEGER',
  float: 'REAL',
  str : 'TEXT',
  bool : 'INT',
  bytes: 'BLOB',
  type(None): 'BLOB', # blob affinity has no conversion preference, so is most appropriate for unknown types.
}

py_to_sql_types_tuple = tuple(py_to_sql_types)

sql_to_py_types = { sql : py for (py, sql) in py_to_sql_types.items() }
