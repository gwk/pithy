# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter
from dataclasses import replace
from typing import Any, Iterable
from warnings import warn

from pithy.strings import abbr_initials, str_tree, str_tree_pairs
from pithy.url import fmt_url
from starlette.datastructures import QueryParams
from starlette.exceptions import HTTPException
from starlette.requests import Request

from ...html import (A, Details, Div, Form, H1, HtmlNode, Input, Label, MuChild, Pre, Present, Script, Select, Summary,
  Table as HtmlTable, Tbody, Td, Th, Thead, Tr)
from ...html.parse import linkify
from ...html.parts import pagination_control
from ...sqlite import Conn, Row
from ...sqlite.keywords import sqlite_keywords
from ...sqlite.parse import sql_parse_schema_table
from ...sqlite.schema import Column, Schema, Table
from ...sqlite.util import sql_quote_entity as qe, sql_quote_val as qv
from .vis import CellRenderFn, ValRenderFn, Vis


class TableAbbrs:

  def __init__(self, *, schema:str, table:str, all_vis:Iterable[Vis]) -> None:
    self.schema_abbrs = TableAbbrs.abbreviate_schema_names({schema, *(vis.fk_schema for vis in all_vis)})
    self.table_abbrs = Counter[str]()
    self.table_abbr = self.unique_abbr(schema, table) # The primary table takes the first, non-numbered abbreviation.

  @staticmethod
  def abbreviate_schema_names(schema_names:set[str]) -> dict[str,str]:
    if len(schema_names) <= 1: return { n : '' for n in schema_names } # If only one schema is present then we can omit it.
    tree = str_tree(sorted(schema_names))
    # We abbreviate by adding the first unique letter to each common prefix.
    return { prefix+suffix : prefix+suffix[:1] for prefix, suffix in str_tree_pairs(tree) }

  def simple_abbr(self, schema:str, table:str) -> str:
    'Generate a table abbreviation without concern for collision with other tables.'
    s = self.schema_abbrs[schema]
    t = abbr_initials(table)
    return f'{s}{t}'

  def unique_abbr(self, schema:str, table:str) -> str:
    '''
    Generate a unique table abbreviation for use within the query.
    Where simple_abbr would collide with a previously issued abbreviation, adds a number suffix.
    If the first abbreviation is an SQL keyword, it gets the suffix 0, so that the numbered sequence remains consistent.
    '''
    abbr = self.simple_abbr(schema, table)
    key = abbr.upper() # SQL identifiers are case-insensitive.
    n = self.table_abbrs[key]
    self.table_abbrs[key] += 1
    if n: return f'{abbr}{n}'
    if key in sqlite_keywords: return f'{abbr}0'
    return abbr



class DbView:
  '''
  An object that provides a web interface for running SQL queries.
  The `where` and `order_by` params are interpolated into the query as raw SQL, so the endpoint must be restricted to trusted users.
  `render` refuses connections that do not have `PRAGMA query_only` set.
  Note that `mode='ro'` alone is insufficient, because it still permits writes to temp tables and writable attached databases.
  '''

  def __init__(self,
    schemas:Iterable[Schema],
    vis: dict[str,dict[str,dict[str,Vis|bool]]], # Maps schema -> table -> column -> Vis|bool.
    order_by: dict[str,dict[str,str]]|None=None,
  ) -> None:

    self.schemas = { s.name : s for s in schemas }
    self.validate_vis(vis)

    def _vis_for(schema:str, table:str, col:str) -> Vis:
      try: v = vis[schema][table][col]
      except KeyError: return Vis(show=True)
      else:
        if isinstance(v, Vis):
          if v.key and not v.fk_schema: # Resolve an unqualified key to the schema of the table being viewed.
            v = replace(v, key=f'{qe(schema)}.{v.key}')
          return v
        elif isinstance(v, bool): return Vis(show=v)
        else: raise TypeError(f'invalid vis; schema={schema!r}, table={table!r}, col={col!r}; vis: {v!r}')

    self.vis:dict[str,dict[str,dict[str,Vis]]] = {
      s.name : { t.name : { c.name : _vis_for(s.name, t.name, c.name) for c in t.columns} for t in s.tables } for s in schemas }

    self.order_by:dict[str,dict[str,str]] = { s.name : {} for s in schemas }
    if order_by:
      for schema_name, schema_d in order_by.items():
        if schema_name not in self.order_by:
          raise ValueError(f'invalid `order_by` schema name: {schema_name!r}; valid names: {self.schemas.keys()}')
        schema = self.schemas[schema_name]
        for table_name, order_by_clause in schema_d.items():
          if table_name not in schema.tables_dict:
            raise ValueError(f'invalid `order_by` table name in schema {schema_name!r}: {table_name!r}; '
              f'valid names: {schema.tables_dict.keys()}')
          self.order_by[schema_name][table_name] = order_by_clause


  def validate_vis(self, vis:dict[str,dict[str,dict[str,Vis|bool]]]) -> None:
    'Raise ValueError for any `vis` key that does not name an existing schema, table or column, including foreign keys.'
    for schema_name, schema_d in vis.items():
      schema = self.schemas.get(schema_name)
      if schema is None: raise ValueError(f'invalid `vis` schema name: {schema_name!r}; valid names: {self.schemas.keys()}')
      for table_name, table_d in schema_d.items():
        table = schema.tables_dict.get(table_name)
        if table is None:
          raise ValueError(f'invalid `vis` table name in schema {schema_name!r}: {table_name!r}; '
            f'valid names: {schema.tables_dict.keys()}')
        for col_name, v in table_d.items():
          if col_name not in table.columns_dict:
            raise ValueError(f'invalid `vis` column name in table {schema_name!r}.{table_name!r}: {col_name!r}; '
              f'valid names: {table.columns_dict.keys()}')
          if isinstance(v, Vis) and v.key:
            fk_schema = self.schemas.get(v.fk_schema or schema_name)
            if fk_schema is None: raise ValueError(f'invalid `vis` key schema for {schema_name}.{table_name}.{col_name}: {v.key!r}')
            fk_table = fk_schema.tables_dict.get(v.fk_table)
            if fk_table is None: raise ValueError(f'invalid `vis` key table for {schema_name}.{table_name}.{col_name}: {v.key!r}')
            if v.fk_col not in fk_table.columns_dict:
              raise ValueError(f'invalid `vis` key column for {schema_name}.{table_name}.{col_name}: {v.key!r}')
            if v.col not in fk_table.columns_dict:
              raise ValueError(f'invalid `vis` col for {schema_name}.{table_name}.{col_name}: {v.col!r}; '
                f'valid names: {fk_table.columns_dict.keys()}')


  def render(self, request:Request, conn:Conn) -> Div:
    '''
    Render a div representing the controls and optionally the DB query result from the request.
    '''
    if not conn.run('PRAGMA query_only').one_col():
      raise ValueError('DbView.render requires a connection with PRAGMA query_only set.')

    path = request.url.path
    params = request.query_params

    if nst := self.get_schema_table(params):
      table_name, schema, table = nst
      table_vis = self.vis[schema.name][table.name]
      abbrs = TableAbbrs(schema=schema.name, table=table.name, all_vis=table_vis.values())

      # Enabled columns.
      col_names = {c.name for c in table.columns}
      en_col_names = set(
        [k[2:] for k in params if k.startswith('c-') and k[2:] in col_names] # Ignore stale params from other tables.
        or [c.name for c in table.columns if table_vis[c.name].show]
        or [table.columns[0].name])

      en_col_spans = [
        Label(cl='en-col', _=[
          Input(name=f'c-{col.name}', type='checkbox', checked=Present(col.name in en_col_names)),
          col.name])
        for col in table.columns]

      order_by:str = params.get('order_by', '') or self.order_by[schema.name].get(table.name, '')

      if not order_by and not table.primary_key: # Use implied ordering for compound keys.
        if (primary_col := table.primary_column) and primary_col.datatype is int:
          # Order by descending to see most recent rows first.
          order_by = f'{abbrs.table_abbr}.{primary_col.name} DESC'

    else:
      table_name = ''
      schema = None
      table = None
      abbrs = None
      en_col_names = set()
      en_col_spans = []
      order_by = ''

    table_names = [f'{qe(s.name)}.{qe(t.name)}' for s in self.schemas.values() for t in s.tables]
    if table_name: assert table_name in table_names # Sanity check that these generated table names match the parsed table name.

    div = Div(cl='dbview')

    div.append(dbview_ui_script())
    div.append(H1(A(href=path, _='SELECT')))

    form = div.append(Form(cl='kv-grid-max', action=path, autocomplete='off'))
    #^ autocomplete off is important for the table select input,
    #^ which otherwise remembers the current value when the user presses the back button.

    form.extend(
      Label('Table:'),
      Div(Select(name='table',
        onchange='findId("columns").replaceChildren(); \
          findSelAll(".clear-on-table-change").forEach(resetValueOfEl); \
          this.form.submit()')
        .options(placeholder='Table', value=table_name, options=table_names)),

      Label('Distinct:'),
      Div(Input(name='distinct', type='checkbox', checked=Present(params.get('distinct')))),

      Label('Columns:'),
      Div(id='columns', cl='clear-on-table-change', _=[
        *en_col_spans,
        Input(type='button', value='All', onclick='updateAllColCheckboxes(true)'),
        Input(type='button', value='None', onclick='updateAllColCheckboxes(false)'),
      ]),

      Label('Where:'),
      Input(name='where', type='search', value=params.get('where', ''), cl='clear-on-table-change'),

      Label('Order by:'),
      Input(name='order_by', type='search', value=order_by,  cl='clear-on-table-change'),

      Label('Limit:'),
      Div(Input(name='limit', type='search', value=params.get('limit', '100'), default=100, cl='clear-on-table-change')),

      Label('Offset:'),
      Div(Input(name='offset', type='search', value=params.get('offset', '0'), default=0,  cl='clear-on-table-change')),

      Label(),
      Div(Input(type='submit', value='Run Query')),
    )

    if table_name:
      assert schema
      assert table
      assert abbrs is not None
      assert order_by is not None
      div.extend(
        self.render_table(conn=conn, schema=schema, table=table, abbrs=abbrs, path=path, params=params,
          en_col_names=en_col_names, order_by=order_by))

    return div


  def get_schema_table(self, params:QueryParams) -> tuple[str,Schema,Table]|None:

    # The 'table' param is qualified and quoted, (e.g. 'schema.table' or '"some schema"."some table"').
    try: full_name = params['table']
    except KeyError: return None

    try: schema_name, table_name = sql_parse_schema_table(full_name)
    except ValueError as e: raise HTTPException(400, f'invalid table name: {full_name!r} ({e})')

    try: schema = self.schemas[schema_name]
    except KeyError: raise HTTPException(400, f'invalid schema: {schema_name!r}')

    try: table = schema.tables_dict[table_name]
    except KeyError: raise HTTPException(400, f'invalid table: {table_name!r}')

    return full_name, schema, table


  def render_table(self, *, conn:Conn, schema:Schema, table:Table, abbrs:TableAbbrs, path:str, params:QueryParams,
   en_col_names:set[str], order_by:str) -> list[HtmlNode]:

    assert en_col_names # Need at least one enabled column to render.

    distinct = bool(params.get('distinct'))

    en_cols = [c for c in table.columns if c.name in en_col_names]

    where = params.get('where', '')

    limit = int_param(params, 'limit', default=100, min=1)
    offset = int_param(params, 'offset', default=0, min=0)

    table_vis = self.vis[schema.name][table.name]

    columns_part, from_clause, col_headers, render_cell_fns = fmt_select_cols(
      schema=schema.name, table=table.name, abbrs=abbrs, path=path, cols=en_cols, table_vis=table_vis)

    distinct_clause = (' DISTINCT' if distinct else '')
    where_clause = f'\nWHERE {where}' if where else ''
    order_by_clause = f'\nORDER BY {order_by}' if order_by else ''

    query = f'SELECT{distinct_clause}{columns_part}{from_clause}{where_clause}{order_by_clause}\nLIMIT {limit} OFFSET {offset}'

    c = conn.cursor()
    error = ''
    try:
      plan = fmt_query_plan(c.run(f'EXPLAIN QUERY PLAN {query}'))
    except Exception as e:
      error = f'Explain query failed: {e}'
      plan = ''

    rows = []
    if not error:
      try: c = c.run(query)
      except Exception as e:
        error = f'Query failed: {e}'
      else:
        rows = [Tr(_=[rcf(row) for rcf in render_cell_fns]) for row in c]

    count:int|None = None
    if not error:
      if 0 < len(rows) < limit: count = offset + len(rows)
      else:
        try:
          if distinct:
            # Always count via a subquery; `COUNT(DISTINCT x)` ignores NULLs (unlike `SELECT DISTINCT`),
            # and a single enabled column can produce multiple select columns.
            count_query = f'SELECT COUNT() FROM (SELECT DISTINCT{columns_part}{from_clause}{where_clause})'
          else:
            count_query = f'SELECT COUNT(){from_clause}{where_clause}'
          count = c.run(count_query).one_col()
        except Exception as e:
          error = f'Count query failed: {e}'


    parts:list[HtmlNode] = [
      Details(Summary('Query'), _=Pre(cl='detail', _=query)),
    ]

    if plan:
      parts.append(Details(Summary('Plan'), Pre(cl='detail', _=plan)))

    if error:
      parts.append(Details(Summary('Error'), Pre(cl='detail', _=error), open=''))
    else:
      pagination = Div(id='pagination', cl='kv-grid-max',
        _=pagination_control(count=count, limit=limit, offset=offset, params=params))
      parts.extend([
        pagination,
        Div(id='results', _=HtmlTable(
          Thead(Tr(_=col_headers)),
          Tbody(_=rows))),
        pagination,
      ])

    return parts


def fmt_query_plan(rows:Iterable[Row]) -> str:
  'Format EXPLAIN QUERY PLAN rows (id, parent, notused, detail) as indented lines.'
  depths = {0: 0} # The root parent id is 0.
  lines = []
  for id_, parent, _, detail in rows:
    depth = depths.get(parent, 0)
    depths[id_] = depth + 1
    lines.append('  ' * depth + detail)
  return '\n'.join(lines)


def int_param(params:QueryParams, name:str, *, default:int, min:int) -> int:
  'Parse an optional integer query parameter, raising a 400 error if it is malformed or less than `min`.'
  raw = params.get(name, '')
  if not raw: return default
  try: val = int(raw)
  except ValueError: raise HTTPException(400, f'invalid {name}: {raw!r}')
  if val < min: raise HTTPException(400, f'invalid {name}: {val}; must be at least {min}')
  return val


sentinel_str = '\x10\xf8'
sentinel_sql = 'char(0x10, 0xF8)'

def fmt_select_cols(schema:str, table:str, abbrs:TableAbbrs, path:str, cols:list[Column], table_vis:dict[str,Vis]
 ) -> tuple[str,str,list[Th],list[CellRenderFn]]:
  '''
  Return "[cols...]", "FROM/JOIN ...", the rendered table header names, and a list of render functions for each column.
  The columns string has a leading space.
  The from string has a leading newline.
  '''

  column_parts:list[str] = []
  line_len = 0
  def append_col_part(col_name:str) -> None:
    'Append a column name to the SELECT clause, wrapping lines as needed.'
    nonlocal line_len
    if column_parts:
      column_parts.append(',')
      line_len += 1
    if line_len + len(col_name) >= 128:
      column_parts.append('\n  ')
      line_len = 2
    else:
      column_parts.append(' ')
      line_len += 1
    column_parts.append(col_name)
    line_len += len(col_name)

  t_abbr = abbrs.table_abbr

  from_parts:list[str] = [f'\nFROM {qe(schema)}.{qe(table)} AS {t_abbr}']

  col_headers = []
  render_cell_fns:list[CellRenderFn] = []

  for col in cols:
    qcol = qe(col.name)
    qual_col = f'{t_abbr}.{qcol}'
    vis = table_vis[col.name]
    if vis.key:
      # Generate a scalar subquery to show the desired visualization column.
      # We need to select two columns: the actual column value (for the tooltip and link),
      # and the subquery value for the visible text.
      th = Th(Details(Summary(cl='disclosure-flush', _=qcol), f'{qe(vis.fk_table)}.{qe(vis.col)}')) # The column header.
      sq_col_name = f'{col.name}:{vis.fk_schema}.{vis.fk_table}.{vis.col}' # The subquery column needs a unique name.
      sq_t_abbr = abbrs.unique_abbr(vis.fk_schema, vis.fk_table)
      #^ The subquery table abbreviation, used in the correlated scalar subquery.
      append_col_part(qcol) # The actual column value is needed to render the tooltip and link.

      nonzero_clause = f'{qual_col}!=0 AND ' if vis.nonzero else ''
      append_col_part(f'(SELECT IFNULL({sq_t_abbr}.{qe(vis.col)}, {sentinel_sql}) FROM {vis.fk_schema_table} AS {sq_t_abbr}'
        f' WHERE {nonzero_clause}{sq_t_abbr}.{qe(vis.fk_col)}={qual_col}) AS {qe(sq_col_name)}')

      cell_fn = mk_cell_sq(col, vis, sq_col_name=sq_col_name, app_path=path, render_fn=vis.render, renders_row=vis.renders_row)
    else:
      th = Th(col.name)
      append_col_part(qcol)
      if vis.render:
        cell_fn = mk_cell_rendered(col, render_fn=vis.render, renders_row=vis.renders_row)
      else:
        cell_fn = mk_cell_plain(col)
    col_headers.append(th)
    if vis.cl:
      cell_fn = mk_cl_wrapper(cell_fn, vis.cl)
    render_cell_fns.append(cell_fn)

  return ''.join(column_parts), ''.join(from_parts), col_headers, render_cell_fns


def mk_cell_plain(col:Column) -> CellRenderFn:
  '''
  Create a cell value rendering function for the given column, with no join or render customization.
  '''
  def cell_plain(row:Row) -> Td:
    val = row[col.name]
    if val is None: return Td(cl='null', _='NULL')
    return Td(_=linkify(str(val)))

  return cell_plain


def mk_cell_rendered(col:Column, render_fn:ValRenderFn, renders_row:bool) -> CellRenderFn:
  '''
  Create a cell value rendering function for the given column, with no join but a custom render function.
  '''

  def cell_rendered(row:Row) -> Td:
    val = row[col.name]
    cl, display_val = try_vis_render(render_fn, val, row if renders_row else val)
    return Td(cl=cl, _=display_val)

  return cell_rendered


def mk_cell_sq(col:Column, vis:Vis, *, sq_col_name:str, app_path:str, render_fn:ValRenderFn|None, renders_row:bool) \
 -> CellRenderFn:
  '''
  Create a cell value rendering function for the given column (with subquery), and possibly a custom render function.
  '''
  assert vis.key
  assert sq_col_name

  def cell_sq(row:Row) -> Td:
    val = row[col.name]
    sq_val = row[sq_col_name]
    if sq_val is None: # The subquery returned no match.
      if val is None:
        return Td(cl='unjoined null', _='NULL')
      else:
        return Td(cl='unjoined', _=val)
    display_val: MuChild
    if sq_val == sentinel_str: # The subquery matched but the value was NULL, converted to the sentinel string.
      cl = 'null'
      display_val = 'NULL'
    elif render_fn:
      cl, display_val = try_vis_render(render_fn, sq_val, row if renders_row else sq_val)
    elif sq_val == '':
      cl = 'empty'
      display_val = 'EMPTY'
    else:
      cl = ''
      display_val = str(sq_val)
    where = f'{qe(vis.fk_col)}={qv(val)}'
    return Td(cl=('joined', cl), _=A(href=fmt_url(app_path, table=vis.fk_schema_table, where=where), title=val, _=display_val))

  return cell_sq


def mk_cl_wrapper(cell_fn:CellRenderFn, cl:str) -> CellRenderFn:
  '''
  Create a cell value rendering function that wraps the given cell function and adds the given CSS class to the result cell.
  '''
  def cell_cl_wrapper(row:Row) -> Td:
    td = cell_fn(row)
    td.append_class(cl)
    return td

  return cell_cl_wrapper


def try_vis_render(render_fn:ValRenderFn, val:Any, render_arg:Any) -> tuple[str,MuChild]:
  '''
  Try to render the given value using the given render function.
  Returns (css_class, rendered_value).
  Catches and logs exceptions, returning an error class/value pair.
  '''
  if val is None: return ('null', 'NULL')
  try:
    rendered = render_fn(render_arg)
    if not isinstance(rendered, MuChild): rendered = str(rendered)
    return ('', rendered)
  except Exception as e:
    warn(f'vis render error; fn={getattr(render_fn, "__qualname__", repr(render_fn))}; exc={e}; {val=!r}')
    return ('error', str(val))



def dbview_ui_script() -> Script:
  return Script('''
  function updateAllColCheckboxes(checked) {
    const checkboxes = document.querySelectorAll('.en-col input[type="checkbox"]');
    checkboxes.forEach(el => el.checked = checked);
  }
  ''')
