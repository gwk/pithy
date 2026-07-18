# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from functools import cache, lru_cache
from typing import Any, get_args, Iterable, Mapping, NamedTuple

from ..encode import encode_obj
from ..frozendicts import frozendict
from ..json import render_json
from .keywords import sqlite_keywords


type SqliteDatatype = None|bool|bytes|float|int|str
#^ The set of types that sqlite3 binds natively; `bool` is included for clarity although it is a subclass of `int`.

sqlite_datatypes:tuple[type,...] = get_args(SqliteDatatype.__value__)


OnConflictTarget  = str|tuple[str,...]


@dataclass(frozen=True)
class SqlExpr:
  '''
  A raw SQL expression, substituted verbatim in place of a value placeholder in generated statements.
  The SQL text is not escaped, so it is caller-trusted, like the `where`, `into` and `with_` statement parameters.
  '''
  sql:str


CURRENT_DATE = SqlExpr('CURRENT_DATE')
CURRENT_TIME = SqlExpr('CURRENT_TIME')
CURRENT_TIMESTAMP = SqlExpr('CURRENT_TIMESTAMP')

CURRENT_TIMESTAMP_Z = SqlExpr("(CURRENT_TIMESTAMP||'Z')")
#^ CURRENT_TIMESTAMP is UTC but bears no timezone marker; the 'Z' suffix makes the stored timestamp explicitly UTC.


type SqlExprs = frozendict[str,SqlExpr]
#^ A mapping of field names to raw SQL expressions; frozendict is hashable, so it can pass through the cached statement builders.


@lru_cache
def insert_head_stmt(*, with_:str='', or_:str='FAIL', into:str, fields:tuple[str,...]) -> str:
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
def insert_values_stmt(*, with_:str='', or_:str='FAIL', into:str, fields:tuple[str,...],
 on_conflict:OnConflictTarget='', returning:tuple[str,...]|str|None=None, exprs:SqlExprs=frozendict()) -> str:
  '''
  Create an INSERT statement that uses named placeholders for values.
  Fields present in `exprs` get their raw SQL text substituted in place of a placeholder.
  '''
  head = insert_head_stmt(with_=with_, or_=or_, into=into, fields=fields)
  if fields:
    placeholders = ', '.join(placeholders_for_fields(fields, exprs))
    values_clause = f'VALUES ({placeholders})'
  else:
    values_clause = 'DEFAULT VALUES'
  parts = [head, values_clause]

  if on_conflict:
    if isinstance(on_conflict, (str, tuple)):
      parts.append(on_conflict_clause(on_conflict, fields=fields))
    else:
      raise NotImplementedError('Multiple ON CONFLICT clauses are not supported yet.')

  if returning:
    if isinstance(returning, tuple): r = ', '.join(returning)
    elif isinstance(returning, str): r = returning
    parts.append(f'RETURNING {r}')

  return ' '.join(parts)


def on_conflict_clause(str_or_pair:str|tuple[str,...], fields:tuple[str,...]) -> str:
  '''
  Create an ON CONFLICT clause for an INSERT statement.
  The DO UPDATE SET assignments reference `excluded.<col>` (the value that would have been inserted) rather than placeholders,
  so the clause adds no statement parameters.
  '''
  if isinstance(str_or_pair, str):
    conflict_targets:tuple[str,...] = (str_or_pair,)
  else:
    conflict_targets = str_or_pair
    if not conflict_targets: raise ValueError('ON CONFLICT target columns cannot be empty')
  included_cols = tuple(f for f in fields if f not in conflict_targets)

  parts = ['ON CONFLICT', '(', ', '.join(conflict_targets), ')', 'DO']

  if included_cols:
    parts.append('UPDATE SET')
    assignments = ', '.join(f'{col}=excluded.{col}' for col in included_cols)
    parts.append(assignments)
  else:
    parts.append('NOTHING')

  return ' '.join(parts)


@lru_cache
def update_stmt(*, with_:str='', or_:str='FAIL', table:str, fields:tuple[str,...], where:str='',
 exprs:SqlExprs=frozendict()) -> str:
  '''
  Create an UPDATE statement that uses named placeholders for values.
  Fields present in `exprs` get their raw SQL text substituted in place of a placeholder.
  '''
  assert or_ in {'ABORT', 'FAIL', 'IGNORE', 'REPLACE', 'ROLLBACK'}
  assert fields
  assignments = ', '.join(f'{f}={p}' for (f, p) in zip(fields, placeholders_for_fields(fields, exprs)))
  with_phrase= f'WITH {with_} ' if with_ else ''
  where_phrase = f' WHERE {where}' if where else ''
  return f'{with_phrase}UPDATE OR {or_} {table} SET {assignments}{where_phrase}'


_sql_substitute_re = re.compile(r'''(?x)
    '(?:[^']|'')*'          # Single-quoted string literal; a doubled quote is an escape.
  | "(?:[^"]|"")*"          # Double-quoted name; a doubled quote is an escape.
  | --[^\n]*                # Line comment; extends to the end of the line.
  | /\*(?s:.*?)(?:\*/|$)    # Block comment; does not nest and may be unterminated at the end of the query.
  | :(?P<name>[A-Za-z_]\w*) # Named placeholder.
  ''')


def sql_substitute_exprs(query:str, args:Mapping[str,Any]) -> tuple[str,dict[str,Any]]:
  '''
  Replace each named `:name` placeholder in `query` whose argument value is a `SqlExpr` with the expression's raw SQL text.
  Return the substituted query and the remaining arguments to be bound.
  The query is scanned with a minimal lexer that recognizes single-quoted string literals, double-quoted names and comments.
  A ValueError is raised if a `SqlExpr` argument has no matching placeholder.
  An expression may itself reference other named placeholders, which will be bound from the remaining arguments as usual.
  '''
  exprs = {k: v for k, v in args.items() if isinstance(v, SqlExpr)}
  remaining = {k: v for k, v in args.items() if not isinstance(v, SqlExpr)}
  if not exprs: return query, remaining

  substituted:set[str] = set()

  def replace(m:re.Match[str]) -> str:
    name = m['name']
    if name is None: return m[0] # String literal, double-quoted name or comment.
    try: expr = exprs[name]
    except KeyError: return m[0] # A placeholder to be bound normally.
    substituted.add(name)
    return expr.sql

  sub_query = _sql_substitute_re.sub(replace, query)

  if unmatched := exprs.keys() - substituted:
    raise ValueError(f'SqlExpr arguments have no matching placeholders: {sorted(unmatched)}; query: {query!r}')
  return sub_query, remaining


def placeholders_for_fields(fields:tuple[str,...], exprs:SqlExprs=frozendict()) -> list[str]:
  '''
  Given a sequence of field names, return a list of named placeholders.
  Fields present in `exprs` get their raw SQL text instead of a placeholder.
  '''
  placeholders = []
  for f in fields:
    if f in exprs:
      placeholders.append(exprs[f].sql)
    else:
      if not f.isidentifier(): raise ValueError(f'field name cannot be used as placeholder: {f!r}')
      placeholders.append(':' + f)
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


def sqlite_native_val(obj:Any) -> SqliteDatatype:
  '''
  Convert `obj` to a value that sqlite3 binds natively.
  `date`, `datetime` and `time` values are converted to ISO-8601 strings using the same `encode_obj` functions as JSON
  rendering, so that a value passed as a top-level statement argument renders identically to the same value embedded in a
  JSON document. All other non-native values are rendered as JSON.
  '''
  if isinstance(obj, sqlite_datatypes): return obj # type: ignore[return-value]
  if isinstance(obj, (date, time)): return encode_obj(obj) # type: ignore[no-any-return]
  if isinstance(obj, SqlExpr):
    raise TypeError(
      f'SqlExpr cannot be bound as a statement argument; substitution requires named arguments or statement generators: {obj!r}')
  return render_json(obj, indent=None)


def forbid_default_adapters_and_converters() -> None:
  '''
  Replace the deprecated sqlite3 default adapters and converters with implementations that raise TypeError.

  The sqlite3 default `date` and `datetime` adapters and converters are deprecated as of Python 3.12.
  pithy.sqlite does not rely on them and instead uses `sqlite_native_val` to convert all arguments explicitly.
  Call this function to install `forbidden_adapter` and `forbidden_converter`,
  which will cause any code that still relies on the sqlite3 defaults fail.
  NOTE: adapter/converter registration is global, so this affects all sqlite3 connections in the process.
  '''
  from sqlite3 import register_adapter, register_converter

  def forbidden_adapter(obj:date) -> str:
    raise TypeError(f'sqlite3 default adapters are forbidden; convert values explicitly, e.g. with sqlite_native_val: {obj!r}')

  def forbidden_converter(data:bytes) -> str:
    raise TypeError(f'sqlite3 default converters are forbidden; convert column values explicitly: {data!r}')

  register_adapter(date, forbidden_adapter)
  register_adapter(datetime, forbidden_adapter)
  register_converter('date', forbidden_converter)
  register_converter('timestamp', forbidden_converter)


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
  time: 'TEXT',
  NoneType: 'BLOB', # None gets treated as NULL. 'BLOB' is considered the most generic type.
}

static_types_to_strict_sqlite:dict[Any,str] = {
  Any: 'ANY',
  time: 'TEXT',
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
  time: str,
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


def sql_comment_lines(comment:str, indent:str='') -> list[str]:
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


def sql_quote_entity(entity:str, always:bool=False) -> str:
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
