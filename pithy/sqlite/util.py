# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any, Dict, NamedTuple, Tuple, Type

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


def _wrapped_type_for_optional(static_type:type) -> type:
  # Optionals are really unions, which are a pain to work with at runtime.
  try: meta_class_name = static_type.__class__.__name__
  except AttributeError as e: raise TypeError(static_type) from e
  if meta_class_name != '_Union': raise TypeError(static_type)
  members = static_type.__args__ # type: ignore
  if len(members) != 2 or NoneType not in members: raise TypeError(static_type)
  return [m for m in members if m is not NoneType][0] # type: ignore


def _default_to_json(obj:Any) -> Any:
  if isinstance(obj, py_to_sql_types_tuple): return obj
  return render_json(obj)


def fields_of(class_:type) -> Tuple[str, ...]:
  if issubclass(class_, NamedTuple): return class_._fields
  # TODO: support dataclasses.
  raise TypeError(class_)


NoneType = type(None)

py_to_sql_types:Dict[type, str] = {
  int : 'INTEGER',
  float: 'REAL',
  str : 'TEXT',
  bool : 'INT',
  bytes: 'BLOB',
  type(None): 'BLOB', # blob affinity has no conversion preference, so is most appropriate for unknown types.
}

py_to_sql_types_tuple = tuple(py_to_sql_types)

sql_to_py_types = { sql : py for (py, sql) in py_to_sql_types.items() }
