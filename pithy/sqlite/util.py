# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from datetime import date, datetime
from typing import Any, get_args, Iterable, NamedTuple, Tuple, Type

from ..json import render_json


def sql_col_names(dataclass:type) -> str:
  '''
  Given a dataclass or NamedTuple subclass, return a string of comma-separated field names.
  '''
  return ', '.join(fields_of(dataclass))


def sql_col_placeholders(dataclass:type) -> str:
  '''
  Given a dataclass or NamedTuple subclass, return a string of comma-separated SQL named placeholders.
  '''
  return ', '.join(f':{n}' for n in fields_of(dataclass))


def sql_col_decls(class_:Type[NamedTuple], primary:str) -> str:
  '''
  Given a dataclass or NamedTuple subclass, yield a sequence of SQL column declarations for use in a CREATE TABLE statement.
  '''
  decls = []
  for n, static_type in class_.__annotations__.items():
    # Currently supports primitive types and their optionals, and Json.
    try: sql_type = py_to_sqlite_static_types[static_type]
    except KeyError:
      try: unwrapped_type = _wrapped_type_for_optional(static_type)
      except TypeError: sql_type = 'TEXT'
      else: sql_type = py_to_sqlite_static_types.get(unwrapped_type, 'TEXT')
    suffix = f' PRIMARY KEY' if n == primary else ''
    decls.append(f'{n} {sql_type}{suffix}')
  return ', '.join(decls)


def _wrapped_type_for_optional(static_type:type) -> type:
  # Optionals are really unions, which are a pain to work with at runtime.
  try: meta_class_name = static_type.__class__.__name__
  except AttributeError as e: raise TypeError(static_type) from e
  if meta_class_name != '_Union': raise TypeError(static_type)
  args = get_args(static_type)
  if not args or len(args) != 2 or NoneType not in args: raise TypeError(static_type)
  return [a for a in args if a is not NoneType][0] # type: ignore[no-any-return]


def default_to_json(obj:Any) -> Any:
  if isinstance(obj, py_to_sqlite_types_tuple): return obj
  return render_json(obj, indent=None)


def fields_of(class_:type) -> Tuple[str, ...]:
  if issubclass(class_, NamedTuple): return class_._fields
  # TODO: support dataclasses.
  raise TypeError(class_)


NoneType = type(None)

py_to_sqlite_types:dict[type,str] = {
  bool: 'INTEGER', # We must use 'INTEGER' or 'INT' in order to be compatible with SQLite strict tables.
  bytes: 'BLOB',
  date: 'TEXT',
  datetime: 'TEXT',
  dict: 'TEXT',
  float: 'REAL',
  int: 'INTEGER',
  list: 'TEXT',
  object: 'ANY', # Necessary for expressing ANY columns for STRICT tables.
  str: 'TEXT',
  type(None): 'BLOB', # None gets treated as NULL. 'BLOB' is considered the most generic type.
}

# The set of types that are converted by the native sqlite3 module. All others are rendered as JSON, defaulting to their repr.
py_to_sqlite_types_tuple = (bool, bytes, date, datetime, float, int, str, type(None))


py_to_sqlite_static_types:dict[Any,str] = {
  Any: 'ANY',
  **py_to_sqlite_types,
}


def sql_comment_lines(comment:str) -> list[str]:
  return [f'-- {l.rstrip()}' for l in comment.strip().splitlines()]


def sql_comment_inline(comment:str) -> str:
  s = re.sub(r'\s+', ' ', comment)
  return ' -- ' + s


def sql_quote_entity(entity:str, always=False) -> str:
  if always or entity.upper() in sqlite_keyords or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]+', entity):
    return sql_quote_entity_always(entity)
  else:
    return entity


def sql_quote_entity_always(entity:str) -> str:
  if '"' in entity: raise ValueError(f'Cannot quote entity containing double quote: {entity!r}')
  return f'"{entity}"'


def sql_quote_str(s:str) -> str:
  if '\0' in s: raise ValueError(f'Cannot quote string for SQLite containing null byte: {s!r}')
  contents = s.replace("'", "''")
  return f"'{contents}'"


def sql_quote_val(val:Any) -> str:
  if val is None: return 'NULL'
  if isinstance(val, str): return sql_quote_str(val)
  if isinstance(val, (int, float)): return str(val)
  if isinstance(val, bool): return '1' if val else '0'
  if isinstance(val, (date, datetime)): return sql_quote_str(str(val))
  raise ValueError(f'Cannot quote value for SQLite: {val!r}')


def sql_quote_seq(seq:Iterable[Any]) -> str:
  return ', '.join(sql_quote_val(v) for v in seq)


sqlite_keyords = {
  'ABORT',
  'ACTION',
  'ADD',
  'AFTER',
  'ALL',
  'ALTER',
  'ALWAYS',
  'ANALYZE',
  'AND',
  'AS',
  'ASC',
  'ATTACH',
  'AUTOINCREMENT',
  'BEFORE',
  'BEGIN',
  'BETWEEN',
  'BY',
  'CASCADE',
  'CASE',
  'CAST',
  'CHECK',
  'COLLATE',
  'COLUMN',
  'COMMIT',
  'CONFLICT',
  'CONSTRAINT',
  'CREATE',
  'CROSS',
  'CURRENT',
  'CURRENT_DATE',
  'CURRENT_TIME',
  'CURRENT_TIMESTAMP',
  'DATABASE',
  'DEFAULT',
  'DEFERRABLE',
  'DEFERRED',
  'DELETE',
  'DESC',
  'DETACH',
  'DISTINCT',
  'DO',
  'DROP',
  'EACH',
  'ELSE',
  'END',
  'ESCAPE',
  'EXCEPT',
  'EXCLUDE',
  'EXCLUSIVE',
  'EXISTS',
  'EXPLAIN',
  'FAIL',
  'FILTER',
  'FIRST',
  'FOLLOWING',
  'FOR',
  'FOREIGN',
  'FROM',
  'FULL',
  'GENERATED',
  'GLOB',
  'GROUP',
  'GROUPS',
  'HAVING',
  'IF',
  'IGNORE',
  'IMMEDIATE',
  'IN',
  'INDEX',
  'INDEXED',
  'INITIALLY',
  'INNER',
  'INSERT',
  'INSTEAD',
  'INTERSECT',
  'INTO',
  'IS',
  'ISNULL',
  'JOIN',
  'KEY',
  'LAST',
  'LEFT',
  'LIKE',
  'LIMIT',
  'MATCH',
  'MATERIALIZED',
  'NATURAL',
  'NO',
  'NOT',
  'NOTHING',
  'NOTNULL',
  'NULL',
  'NULLS',
  'OF',
  'OFFSET',
  'ON',
  'OR',
  'ORDER',
  'OTHERS',
  'OUTER',
  'OVER',
  'PARTITION',
  'PLAN',
  'PRAGMA',
  'PRECEDING',
  'PRIMARY',
  'QUERY',
  'RAISE',
  'RANGE',
  'RECURSIVE',
  'REFERENCES',
  'REGEXP',
  'REINDEX',
  'RELEASE',
  'RENAME',
  'REPLACE',
  'RESTRICT',
  'RETURNING',
  'RIGHT',
  'ROLLBACK',
  'ROW',
  'ROWS',
  'SAVEPOINT',
  'SELECT',
  'SET',
  'TABLE',
  'TEMP',
  'TEMPORARY',
  'THEN',
  'TIES',
  'TO',
  'TRANSACTION',
  'TRIGGER',
  'UNBOUNDED',
  'UNION',
  'UNIQUE',
  'UPDATE',
  'USING',
  'VACUUM',
  'VALUES',
  'VIEW',
  'VIRTUAL',
  'WHEN',
  'WHERE',
  'WINDOW',
  'WITH',
  'WITHOUT',
}
