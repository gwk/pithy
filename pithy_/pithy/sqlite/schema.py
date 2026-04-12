# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, Iterable, Self

from tolkien import Source

from ..dict import dict_strict_inverse
from ..parse import Syn
from ..transtruct import Input, Transtructor
from .keywords import sqlite_keywords
from .parse import sql_parse_entity, sql_parser
from .util import (nonstrict_to_strict_types_for_sqlite, sql_comment_inline, sql_comment_lines, sql_quote_entity as qe,
  sql_quote_entity_always as qea, strict_sqlite_to_types, types_to_strict_sqlite)


@dataclass(frozen=True, order=True)
class Column:
  '''
  `default`: must be either None, a `signed-number`, `literal-value`, 'CURRENT_DATE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP',
  or an SQL `expr`.
  SQLite column constraints: https://www.sqlite.org/syntax/column-constraint.html
  '''
  name:str
  datatype:type # Note: 'ANY' columns should be expressed with `object` rather than `Any` to mollify the type checker.
  allow_kw:bool = False # Whether the column name is allowed to be a keyword.
  is_opt:bool = False # Whether the column allows NULL. Must be False for primary keys.
  is_primary:bool = False # Whether the column is PRIMARY KEY.
  is_unique:bool = False # Whether the column is UNIQUE.
  virtual:str|None = None
  default:bool|int|float|str|None = None # The default value. None means no default; SQLite will default to NULL.
  desc:str = ''


  def __post_init__(self) -> None:

    name = self.name

    if not self.allow_kw and name.upper() in sqlite_keywords:
      raise ValueError(f'Column name {name!r} is an SQLite keyword. Use `allow_kw=True` to override.')

    if self.is_primary:
      if not self.is_unique: raise ValueError(f'Primary key column {name!r} must be unique.')

    if self.virtual is not None:
      if self.is_primary: raise ValueError(f'Virtual column {name!r} cannot be primary key.')
      if self.default is not None: raise ValueError(f'Virtual column {name!r} cannot have a default value.')

    if self.default is not None:
      if strict_type := nonstrict_to_strict_types_for_sqlite.get(self.datatype):
        if not isinstance(self.default, strict_type):
          raise ValueError(f'Column {name!r} default value {self.default!r} is not of strict type {strict_type.__name__}'
            f' for datatype {self.datatype.__name__}.')
      elif not isinstance(self.default, self.datatype):
        raise ValueError(f'Column {name!r} default value {self.default!r} is not of datatype {self.datatype.__name__}.')


  @cached_property
  def is_non_opt_str(self) -> bool: return self.datatype is str and not self.is_opt

  @property
  def is_generated(self) -> bool: return self.virtual is not None # TODO: add stored column support.

  @cached_property
  def default_rendered(self) -> str: return render_column_default(self.default)


  @property
  def semantic_details(self) -> tuple[bool,bool,bool,(str|None),str]:
    '''
    A tuple of all semantic attributes other than `name` and `datatype`.
    Excludes `allow_kw` and `desc`, which are irrelevant to the generated SQL.
    The rendered string representation of `default` is used because it disambiguates the empty string shorthand case.
    '''
    return (self.is_opt, self.is_primary, self.is_unique, self.virtual, self.default_rendered)


  def diff_hint(self, other:'Column', *, include_name:bool, exact_type:bool) -> str:
    '''
    Return a reason that this column is different from another, ignoring attributes that are not semantically relevant:
    * allow_kw
    * desc

    Note that this is not a symmetric operation if exact_type is False:
    we allow self.datatype to be a nonstrict equivalent type to other.datatype,
    in the sense defined by `nonstrict_to_strict_types_for_sqlite`.
    This allows us to compare a current self from a python schema to a previous version parsed from sqlite_schema.
    '''
    if include_name and self.name != other.name: return f'/ {qea(other.name)} order'
    if self.datatype != other.datatype:
      if exact_type or nonstrict_to_strict_types_for_sqlite.get(self.datatype) != other.datatype:
        return 'datatype'
    if self.is_opt != other.is_opt: return 'is_opt'
    if self.is_primary != other.is_primary: return 'is_primary'
    if self.is_unique != other.is_unique: return 'is_unique'
    if self.virtual != other.virtual: return f'virtual ({self.virtual!r} != {other.virtual!r})'
    if self.default != other.default: return 'default'
    return ''


  def sql(self) -> str:
    name = qe(self.name)
    type_ = types_to_strict_sqlite[self.datatype]
    primary_key = ' PRIMARY KEY' if self.is_primary else ''
    unique = ' UNIQUE' if (self.is_unique and not self.is_primary) else ''
    not_null = '' if self.is_opt else ' NOT NULL'

    if self.virtual is not None:
      virtual = f' AS ({self.virtual}) VIRTUAL'
    else:
      virtual = ''

    if self.default is not None:
      d = self.default
      if isinstance(d, (int, float)):
        ds = str(self.default)
      else:
        assert isinstance(d, str)
        if d == '': ds = "''" # Special affordance for the empty string as shorthand.
        elif d.startswith("'") and d.endswith("'"): ds = d # Quoted string value.
        elif d.startswith('(') and d.endswith(')'): ds = d # SQL expression.
        elif d in ('CURRENT_DATE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP'): ds = d # Special value.
        else: raise ValueError(f'Invalid Column default SQL expression: {d!r}')
      default = f' DEFAULT {ds}'
    else:
      default = ''

    return f'{name} {type_}{primary_key}{unique}{not_null}{virtual}{default}'



class Structure:
  '''
  Top-level SQL "database objects", i.e. Index, Table, Trigger, View.

  We use `sql_quote_entity_always` to quote all structure names because SQLite 3.40 always quotes renamed tables.
  By quoting names in the generated statements, we reduce syntactic discrepancies caused by rename operations.

  Note however that column rename options preserve the quoting as written in the ALTER statement.
  '''

  name:str
  desc:str


  @cached_property
  def quoted_name(self) -> str: return qea(self.name)


  def sql(self, *, schema:str='', name:str='', if_not_exists:bool=False) -> str:
    raise NotImplementedError


  @classmethod
  def parse(cls, name:str, text:str) -> Self:
    '''
    Parse a schema definition from a string.
    '''
    source = Source(name, text)
    ast = sql_parser.parse('create_stmt', source)
    return schema_transtructor.transtruct(cls, ast, ctx=source)


  def diff_hints(self, other:Self) -> list[str]: raise NotImplementedError



class TableDepStructure(Structure):
  'Structure objects that depend on a table, i.e. indexes, triggers, views.'
  table:str



@dataclass(frozen=True, order=True)
class Table(Structure):
  name:str
  desc:str = ''
  is_strict:bool = False
  without_rowid:bool = False
  primary_key:tuple[str,...] = () # The compound primary key, if any. Each string is an SQL expr, not a parsed column name.
  # TODO: foreign keys.
  columns:tuple[Column,...] = ()

  def __post_init__(self) -> None:
    if len(self.columns_dict) != len(self.column_names):
      counter = Counter(self.column_names)
      dups = [n for n, c in counter.items() if c > 1]
      raise ValueError(f'Table {self} has duplicate column names: {dups!r}')

  @cached_property
  def columns_dict(self) -> dict[str, Column]: return {c.name: c for c in self.columns}

  @cached_property
  def column_names(self) -> tuple[str, ...]: return tuple(c.name for c in self.columns)

  @cached_property
  def quoted_column_names(self) -> tuple[str, ...]: return tuple(qe(n) for n in self.column_names)

  @cached_property
  def material_column_names(self) -> tuple[str, ...]: return tuple(c.name for c in self.columns if not c.is_generated)

  @cached_property
  def quoted_columns_str(self) -> str: return ', '.join(qe(n) for n in self.column_names)

  @cached_property
  def quoted_material_columns_str(self) -> str: return ', '.join(qe(n) for n in self.material_column_names)


  @cached_property
  def primary_column(self) -> Column|None:
    for c in self.columns:
      if c.is_primary: return c
    return None


  def sql(self, *, schema:str='', name:str='', if_not_exists:bool=False) -> str:
    if schema and not schema.isidentifier(): raise ValueError(f'Invalid schema name: {schema!r}')

    qual_name = f'{schema}{schema and "."}{qea(name or self.name)}'
    lines:list[str] = []
    if_not_exists_str = 'IF NOT EXISTS ' if if_not_exists else ''
    lines.append(f'CREATE TABLE {if_not_exists_str}{qual_name} (')
    if self.desc: lines.extend(sql_comment_lines(self.desc, indent='  '))

    # Columns are separated by commas, except for the last one.
    # This is complicated by comments following commas,
    # and trailing primary/foreign key lines that are also included within the parens.
    inner_parts = [] # Parts of lines within the parens.
    for c in self.columns:
      column_sql = c.sql()
      comment = sql_comment_inline(c.desc) if c.desc else ''
      inner_parts.append(['  ', column_sql, ',', comment])

    if self.primary_key:
      primary_key_parts = ', '.join(qe(c) for c in self.primary_key)
      inner_parts.append([f'  PRIMARY KEY ({primary_key_parts})', ',', ''])

    # Remove the comma from the last inner line.
    assert inner_parts[-1][-2] == ','
    inner_parts[-1][-2] = '' # Remove last comma.

    lines.extend(''.join(p) for p in inner_parts)

    table_options = [
      ' STRICT' if self.is_strict else '',
      ' WITHOUT ROWID' if self.without_rowid else '',
    ]
    table_options_str = ','.join(opt for opt in table_options if opt)
    lines.append(f'){table_options_str}')

    return '\n'.join(lines)


  def match_columns_by_name(self, other:Self) -> dict[str,Column]:
    '''
    Attempt to match the columns of this table to those of another by name.
    Returns a dict matching self column names to other's columns.
    '''

    od = other.columns_dict
    matches = {}

    for c in self.columns:
      try: oc = od[c.name]
      except KeyError: continue
      assert c.name not in matches
      matches[c.name] = oc

    return matches


  def diff_hints(self, other:Self) -> list[str]:
    if self.name != other.name: return ['name']
    hints = []
    if self.is_strict != other.is_strict: hints.append('is_strict')
    if self.without_rowid != other.without_rowid: hints.append('without_rowid')
    if self.primary_key != other.primary_key: hints.append('primary_key')
    matches = self.match_columns_by_name(other)
    if self.column_names != tuple(matches): hints.append('columns')
    else:
      col_hints = [(c, c.diff_hint(oc, include_name=True, exact_type=False)) for c, oc in zip(self.columns, other.columns)]
      hints.extend(f'{c.name}.{dh}' for c, dh in col_hints if dh)
    return hints



@dataclass(frozen=True, order=True)
class Index(TableDepStructure):
  '''
  A table index.
  `columns` is a tuple of column names or SQL expressions. Note that unlike table columns,
  index columns are not quoted because they can be arbitrary SQL expressions.
  '''

  name:str
  table:str
  is_unique:bool = False
  desc:str = ''
  columns:tuple[str,...] = ()
  where:str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.columns, tuple):
      # Without this, a single str passed as `columns` will be iterated over, resulting in erroneous single-char columns.
      raise TypeError(f'Index.columns must be a tuple; received: {self.columns!r}')


  def sql(self, *, schema:str='', name:str='', if_not_exists:bool=False) -> str:
    if schema and not schema.isidentifier(): raise ValueError(f'Invalid schema name: {schema!r}')

    qual_name = f'{schema}{schema and "."}{qea(name or self.name)}'
    lines = []
    if self.desc:
      lines.append(f'-- {qual_name}')
      lines.extend(sql_comment_lines(self.desc))

    if_not_exists_str = 'IF NOT EXISTS ' if if_not_exists else ''
    unique_str = 'UNIQUE ' if self.is_unique else ''
    lines.append(f'CREATE {unique_str}INDEX {if_not_exists_str}{qual_name}')
    columns_str = ', '.join(self.columns)
    lines.append(f'  ON {qea(self.table)} ({columns_str})')

    if self.where:
      lines.append(f'  WHERE {self.where}')

    return '\n'.join(lines)


  def diff_hints(self, other:Self) -> list[str]:
    if self.name != other.name: return ['name']
    hints = []
    if self.table != other.table: hints.append('table')
    if self.is_unique != other.is_unique: hints.append('is_unique')
    if self.columns != other.columns: hints.append('columns')
    return hints


class Schema:
  name:str
  desc:str
  tables:list[Table]
  indexes:list[Index]


  def __init__(self, name:str='', desc:str='', structures:Iterable[Structure]=()) -> None:
    if name and not name.isidentifier(): raise ValueError(f'Invalid schema name: {self.name!r}')

    self.name = name
    self.desc = desc
    self.tables = []
    self.indexes = []

    names = set()
    for s in structures:
      if s.name in names: raise ValueError(f'Structure {s} has a duplicate name.')
      names.add(s.name)
      if isinstance(s, Table): self.tables.append(s)
      elif isinstance(s, Index): self.indexes.append(s)
      else: raise ValueError(f'Invalid Structure type: {s!r}')


  @property
  def structures(self) -> Iterable[Structure]:
    yield from self.tables
    yield from self.indexes


  @cached_property
  def structures_dict(self) -> dict[str, Structure]:
    return {s.name: s for s in self.structures}


  @cached_property
  def tables_dict(self) -> dict[str, Table]:
    return {t.name: t for t in self.tables}


  @cached_property
  def indexes_dict(self) -> dict[str, Index]:
    return {i.name: i for i in self.indexes}


  @cached_property
  def table_deps(self) -> dict[str, tuple[TableDepStructure,...]]:
    '''
    Return a dict mapping table names to the structures that depend on it.
    '''
    deps = defaultdict[str,set[TableDepStructure]](set)

    for s in self.structures:
      if isinstance(s, TableDepStructure): deps[s.table].add(s)

    return { n : tuple(sorted(deps[n])) for n in self.tables_dict } # type: ignore[type-var]



  def sql(self, *, name:str='', if_not_exists:bool=False) -> Iterable[str]:
    name = name or self.name
    if name and not name.isidentifier(): raise ValueError(f'Invalid schema name: {name!r}')

    if name or self.desc:
      yield '\n'
      if self.name: yield f'-- Schema: {name}\n'
      if self.desc: yield '\n'.join(sql_comment_lines(self.desc)) + '\n'

    for s in self.structures:
      yield '\n'
      yield s.sql(schema=name, if_not_exists=if_not_exists)
      yield ';'
      yield '\n'


  def write_module_sql(self, if_not_exists:bool=False, steps:int=1) -> None:
    '''
    Write an SQL schema file for this schema to the package directory of the caller.
    This is typically called from the main() of a module defining a schema.
    `steps` can be used to adjust the frame introspection level.
    Be careful: if the step count is wrong, the file may be written into an installed package location,
    which is usually not desirable and potentially destructive to the installation.
    '''
    from ..meta import caller_module_spec
    if steps < 1: raise ValueError(f'steps must be >= 1; received {steps!r}')
    spec = caller_module_spec(steps=steps)
    path = spec.origin
    if not path: raise ValueError(f'Cannot determine path of caller module: {spec!r}.')
    if not path.endswith('.py'): raise ValueError(f'Expected a .py file for module; {spec!r}')
    path = path[:-3] + '.sql'
    print(f'Writing SQL schema to {path!r}.')
    with open(path, 'w') as f:
      f.write(''.join(self.sql(if_not_exists=if_not_exists)))


  @classmethod
  def parse(cls, path:str, text:str) -> 'Schema':
    '''
    Parse a schema definition from a string.
    '''
    source = Source(path, text)
    ast = sql_parser.parse('stmts', source)
    return schema_transtructor.transtruct(Schema, ast, ctx=source)



def render_column_default(val:bool|int|float|str|None) -> str:
  match val:
    case None: return 'NULL'
    case bool(): return str(val).upper()
    case int()|float(): return str(val)
    case '': return "''" # Special affordance for the empty string as shorthand.
    case 'CURRENT_DATE'|'CURRENT_TIME'|'CURRENT_TIMESTAMP': return val
    case str():
      if val.startswith("'") and val.endswith("'"): return val # Quoted string or blob value.
      if val.startswith('(') and val.endswith(')'): return val # SQL expression.
      if val.startswith("x'") and val.endswith("'"): raise NotImplementedError('BLOB literals not supported.')
      raise ValueError(f'Invalid Column default SQL expression: {val!r}')
    case _: raise ValueError(f'Invalid Column default: {val!r}')


def unrender_column_default(val:str) -> bool|int|float|str|None:
  '''
  Convert the rendered SQL default value back to a python value.
  This function does not completely validate the rendered string, just converts it back to a python value.
  '''
  if val == 'NULL': return None
  if val == "''": return '' # Special affordance for the empty string as shorthand.
  try: return _bool_repr_to_vals[val.upper()]
  except KeyError: pass
  c = val[0]
  if c in '0123456789.+-': return float(val) if '.' in val else int(val)
  if c == 'x': raise NotImplementedError('BLOB literals not supported.')
  if c in "'(": return val
  if val.startswith('CURRENT_'): return val
  raise ValueError(f'Invalid Column default rendered string: {val!r}')


_bool_repr_to_vals = {'TRUE': True, 'FALSE': False}



schema_transtructor = Transtructor()


@schema_transtructor.prefigure(Column)
def prefigure_Column(class_:type, column:Input, source:Source) -> dict[str,Any]:
  name = sql_parse_entity(source[column.name])
  if column.type_name is None: raise ValueError(f'Column {name!r} has no type.')
  type_name = source[column.type_name]
  datatype = strict_sqlite_to_types[type_name]
  constraints = dict(_parse_column_constraint(cc, source) for cc in column.constraints)
  is_primary = constraints.get('col_primary_key', False)
  is_opt = not constraints.get('not_null', False)
  is_unique = constraints.get('unique', False) or is_primary
  virtual = constraints.get('virtual')
  stored = constraints.get('stored')
  if stored: raise NotImplementedError(f'Column {name!r} is stored.')
  return dict(
    name=name,
    datatype=datatype,
    allow_kw=(name.upper() in sqlite_keywords),
    is_opt=is_opt,
    is_primary=is_primary,
    is_unique=is_unique,
    virtual=virtual,
    default=constraints.get('default'),
  )


def _parse_column_constraint(constraint:Input, source:Source) -> tuple[str,Any]:
  if constraint.constraint_name is not None: raise NotImplementedError(f'column_constraint named constraint: {constraint.constraint_name!r}')
  kind = constraint.kind
  lbl = kind.lbl
  val = kind.val
  match lbl:
    case 'col_primary_key':
      if val.asc_desc is not None: raise NotImplementedError(f'column_constraint primary_key asc_desc: {constraint!r}')
      if val.on_conflict is not None: raise NotImplementedError(f'column_constraint primary_key on_conflict: {constraint!r}')
      if val.AUTOINCREMENT is not None: raise NotImplementedError(f'column_constraint primary_key autoincrement: {constraint!r}')
      return lbl, True
    case 'not_null' | 'unique':
      on_conflict = val
      if on_conflict is not None: raise NotImplementedError(f'column_constraint primary_key on_conflict: {constraint!r}')
      return lbl, True
    case 'check':
      raise NotImplementedError(f'column_constraint check: {constraint!r}')
    case 'default':
      default_val = unrender_column_default(source[val])
      return lbl, default_val
    case 'collate':
      raise NotImplementedError(f'column_constraint collate: {constraint!r}')
    case 'generated_constraint':
      stored_or_virtual = val.stored_or_virtual.lower()
      expr_str = source[val.expr]
      # Hack to remove the parens around the expression.
      assert expr_str.startswith('(') and expr_str.endswith(')')
      expr_str = expr_str[1:-1]
      return stored_or_virtual, expr_str
    case _:
      raise NotImplementedError(f'column_constraint: {constraint!r}')



@schema_transtructor.prefigure(Table)
def prefigure_Table(class_:type, create_temporary:Input, source:Source) -> dict[str,Any]:
  #_is_temporary = create_temporary.is_temporary # TODO: use this.
  table = create_temporary.structure

  table_name_parts = [sql_parse_entity(source[t]) for t in table.name]

  def_ = table.def_
  if not isinstance(def_, sql_parser.types.TableDef): raise ValueError(f'Expected a table_def; received {def_!r}')
  table_options = def_.table_options # type: ignore[attr-defined]
  constraints = dict(_parse_table_constraint(tc, source) for tc in def_.table_constraints) # type: ignore[attr-defined]
  if primary_key := constraints.get('table_primary_key'):
    primary_key_names = tuple(c.expr for c in primary_key)
  else:
    primary_key_names = ()

  column_defs = def_.column_defs # type: ignore[attr-defined]

  return dict(
    name=table_name_parts[-1], # NOTE: we currently discard the schema name if it is present.
    is_strict=('STRICT' in table_options),
    without_rowid=('WITHOUT_ROWID' in table_options),
    primary_key=primary_key_names,
    columns=column_defs,
  )


def _parse_table_constraint(constraint:Input, source:Source) -> tuple[str,Any]:
  '''
  Parse a table constraint. constraint is a TableConstraint generated struct.
  '''
  if constraint.constraint_name is not None:
    raise NotImplementedError(f'Cannot parse constraint_name: {constraint.constraint_name!r}')
  kind:Syn = constraint.kind # A Syn wrapper around the Choice result.
  match kind.lbl:
    case 'table_primary_key':
      indexed_cols = tuple(_parse_indexed_column(c, source) for c in kind.val.indexed_columns)
      if kind.val.on_conflict is not None: raise NotImplementedError(f'Cannot yet parse on_conflict: {kind.val.on_conflict!r}')
      return kind.lbl, indexed_cols
    case _: raise NotImplementedError(f'Cannot parse table constraint {kind.lbl!r}: {constraint!r}')


@dataclass(frozen=True)
class IndexedColumn:
  expr:str
  collate:str|None
  asc_desc:str|None


def _parse_indexed_column(column:Input, source:Source) -> IndexedColumn:
  '''
  The `indexed-column` syntax accepts either a column name or an arbitrary expression.
  see: https://www.sqlite.org/syntax/indexed-column.html
  '''
  expr_syn = column.expr
  expr_text = source[expr_syn]
  return IndexedColumn(expr=expr_text, collate=column.collate, asc_desc=column.asc_desc)


def build_clean_row_record_fn(table:Table, renamed_keys:dict[str,str]|None=None, keep_keys:Iterable[str]=()) \
 -> Callable[[dict[str,Any]],dict[str,Any]]:
  '''
  Create a function that cleans a record dict in preparation for inserting it into the specified database table.
  `renamed_keys` maps record keys to desired table column names.
  `keep_keys` is a container of renamed record keys that are not material column names but should be kept in the result.
  All values in `renamed_keys` must be either names of material columns or new names that are present in `keep_keys`.
  All elements in `keep_keys` must not be material column names.
  This rule is enforced so that `keep_keys` is a clear list of exceptional keys.
  Kept keys do not need to be present in `renamed_keys`.
  '''
  if renamed_keys is None: renamed_keys = {}
  keep_keys = tuple(keep_keys)
  mat_cols = table.material_column_names

  for k, v in renamed_keys.items():
    if v not in mat_cols and v not in keep_keys:
      raise ValueError(f'Invalid renamed key; column name is not a material column of {table.name!r}: {k!r} -> {v!r}')

  for kk in keep_keys:
    if kk in mat_cols:
      raise ValueError(f'Invalid (redundant) keep_keys name; key name is a material column of {table.name!r}: {kk!r}')

  renamed_keys_inv = dict_strict_inverse(renamed_keys) # Columns to record keys.
  for c in mat_cols: # Add in all material columns that are not in renamed_keys.
    if c not in renamed_keys_inv:
      renamed_keys_inv[c] = c
  keys_map = dict_strict_inverse(renamed_keys_inv) # Record keys to columns.

  for kk in keep_keys:
    if kk not in keys_map:
      keys_map[kk] = kk

  replace_none_with_empty_map = {
    c: (table.columns_dict[c].is_non_opt_str if (c in mat_cols) else False) for c in keys_map.values() }

  def build_clean_row_record(record:dict[str,Any]) -> dict[str,Any]:
    d = {}
    for orig_k, v in record.items():
      try: clean_k = keys_map[orig_k]
      except KeyError: continue
      if v is None and replace_none_with_empty_map[clean_k]: v = ''
      d[clean_k] = v
    return d

  return build_clean_row_record
