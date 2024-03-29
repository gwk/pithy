# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from datetime import date, datetime
from functools import cache, lru_cache
from typing import Any, get_args, Iterable, NamedTuple

from ..json import render_json
from .keywords import sqlite_keywords


@lru_cache
def insert_head_stmt(*, with_='', or_='FAIL', into:str, fields:tuple[str,...]) -> str:
    '''
    Create the first part of an INSERT statement, up to the VALUES/SELECT/DEFAULT clause.

    '''
    assert or_ in {'ABORT', 'FAIL', 'IGNORE', 'REPLACE', 'ROLLBACK'}
    if fields:
      if not all(f.isidentifier() for f in fields): raise ValueError(f'invalid field names: {fields!r}')
      fields_joined = ', '.join(sql_quote_entity(f) for f in fields)
      fields_clause = f' ({fields_joined})'
    else:
      fields_clause = ''
    with_space = ' ' if with_ else ''
    return f'{with_}{with_space}INSERT OR {or_} INTO {into}{fields_clause}'


@lru_cache
def insert_values_stmt(*, with_='', or_='FAIL', into:str, named:bool, fields:tuple[str,...],
 returning:tuple[str,...]|str|None=None) -> str:
    '''
    Create an INSERT statement that uses positional or named placeholders for values.
    '''
    head = insert_head_stmt(with_=with_, or_=or_, into=into, fields=fields)
    if fields:
      placeholders = ', '.join(placeholders_for_fields(fields, named))
      values_clause = f' VALUES ({placeholders})'
    else:
      values_clause = ' DEFAULT VALUES'
    stmt = head + values_clause

    if returning:
      if isinstance(returning, tuple): r = ', '.join(returning)
      elif isinstance(returning, str): r = returning
      stmt += f' RETURNING {r}'

    return stmt


@lru_cache
def update_stmt(*, with_='', or_='FAIL', table:str, named:bool, fields:tuple[str,...], where:str='') -> str:
  '''
  Create an UPDATE statement that uses positional or named placeholders for values.
  '''
  assert or_ in {'ABORT', 'FAIL', 'IGNORE', 'REPLCE', 'ROLLBACK'}
  assert fields
  assignments = ', '.join(f'{f}={p}' for (f, p) in zip(fields, placeholders_for_fields(fields, named)))
  with_phrase= f'WITH {with_} ' if with_ else ''
  where_phrase = f' WHERE {where}' if where else ''
  return f'{with_phrase}UPDATE OR {or_} {table} SET {assignments}{where_phrase}'


def placeholders_for_fields(fields:tuple[str,...], named:bool) -> list[str]:
  '''
  Given a sequence of field names, return a string of comma-separated placeholders.
  '''
  if named:
    placeholders = []
    for f in fields:
      if not f.isidentifier(): raise ValueError(f'field name cannot be used as placeholder: {f!r}')
      placeholders.append(':' + f)
  else:
    placeholders = ['?'] * len(fields)
  return placeholders


def col_names_for_dc(dataclass:type) -> str:
  '''
  Given a dataclass or NamedTuple subclass, return a string of comma-separated field names.
  '''
  return ', '.join(fields_of(dataclass))


def col_placeholders_for_dc(dataclass:type) -> str:
  '''
  Given a dataclass or NamedTuple subclass, return a string of comma-separated SQL named placeholders.
  '''
  return ', '.join(f':{n}' for n in fields_of(dataclass))


def col_decls_for_dc(class_:type[NamedTuple], primary:str) -> str:
  '''
  Given a dataclass or NamedTuple subclass, yield a sequence of SQL column declarations for use in a CREATE TABLE statement.
  '''
  decls = []
  for n, static_type in class_.__annotations__.items():
    # Currently supports primitive types and their optionals, and Json.
    try: sql_type = static_types_to_strict_sqlite[static_type]
    except KeyError:
      try: unwrapped_type = _wrapped_type_for_optional(static_type)
      except TypeError: sql_type = 'TEXT'
      else: sql_type = static_types_to_strict_sqlite.get(unwrapped_type, 'TEXT')
    suffix = ' PRIMARY KEY' if n == primary else ''
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
  if isinstance(obj, types_natively_converted_by_sqlite): return obj
  return render_json(obj, indent=None)


def update_to_json(d:dict[str,Any]) -> dict[str,Any]:
  for k, v in d.items():
    if isinstance(v, types_natively_converted_by_sqlite): continue
    d[k] = render_json(v, indent=None)
  return d


def fields_of(class_:type) -> tuple[str, ...]:
  if issubclass(class_, NamedTuple): return class_._fields
  # TODO: support dataclasses.
  raise TypeError(class_)


NoneType:type = type(None)

types_to_strict_sqlite:dict[type,str] = {
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
  NoneType: 'BLOB', # None gets treated as NULL. 'BLOB' is considered the most generic type.
}

# The set of types that are converted by the native sqlite3 module. All others are rendered as JSON, defaulting to their repr.
types_natively_converted_by_sqlite = (bool, bytes, date, datetime, float, int, str, NoneType)

static_types_to_strict_sqlite:dict[Any,str] = {
  Any: 'ANY',
  **types_to_strict_sqlite,
}

strict_sqlite_to_types:dict[str,type] = {
  'ANY': object,
  'BLOB': bytes,
  'INT': int,
  'INTEGER': int,
  'REAL': float,
  'TEXT': str,
}

nonstrict_to_strict_types_for_sqlite = {
  NoneType: bytes,
  bool: int,
  date: str,
  datetime: str,
  dict: str,
  list: str,
}


def type_for_lax_sql(sql_type:str) -> type:
  'Follows the rules in https://www.sqlite.org/datatype3.html#determination_of_column_affinity.'
  s = sql_type.upper()
  try: return strict_sqlite_to_types[s]
  except KeyError: pass
  if 'INT' in s: return int
  if any(t in s for t in ('CHAR', 'CLOB', 'TEXT')): return str
  if 'BLOB' in s: return bytes
  if any(t in s for t in ('REAL', 'FLOA', 'DOUB')): return float
  return object # Note: the default affinity is 'NUMERIC', but it makes more sense to default to 'object'.


def sql_comment_lines(comment:str, indent='') -> list[str]:
  if indent and not indent.isspace(): raise ValueError(f'Indent must be whitespace: {indent!r}')
  return [f'{indent}-- {l.rstrip()}' for l in comment.strip().splitlines()]


def sql_comment_inline(comment:str) -> str:
  comment = re.sub(r'\n+\s*', ' ', comment)
  comment = re.sub(r'\s+', ' ', comment)
  return ' -- ' + comment.strip()


def sql_fuzzy_match_words(query:str) -> str:
  words = query.strip().split()
  return f'{"%".join(words)}%'


def sql_fuzzy_search_words(query:str) -> str:
  words = query.strip().split()
  return f'%{"%".join(words)}%'


def sql_quote_qual_entity(*entity_parts:str) -> str:
  return '.'.join(sql_quote_entity(p) for p in entity_parts if p)


def sql_quote_entity(entity:str, always=False) -> str:
  if always or entity.upper() in sqlite_keywords or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', entity):
    return sql_quote_entity_always(entity)
  else:
    return entity


@cache
def sql_cache_quote_col_names(col_names:tuple[str]) -> str:
  return ', '.join(sql_quote_entity(c) for c in col_names)


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
