# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter
from typing import Any, Callable, Iterable
from warnings import warn

from pithy.string import str_tree, str_tree_pairs
from pithy.url import fmt_url
from starlette.datastructures import QueryParams
from starlette.exceptions import HTTPException
from starlette.requests import Request

from ...html import (A, Details, Div, Form, H1, HtmlNode, Input, Label, MuChild, Pre, Present, Script, Select, Summary,
  Table as HtmlTable, Tbody, Td, Th, Thead, Tr)
from ...html.parse import linkify
from ...html.parts import pagination_control
from ...sqlite import Conn, Row, SqliteError
from ...sqlite.parse import sql_parse_schema_table
from ...sqlite.schema import Column, Schema, Table
from ...sqlite.util import sql_quote_entity as qe, sql_quote_val as qv
from .vis import Vis


ValRenderFn = Callable[[Any],Any]
CellRenderFn = Callable[[Any],Td]


class TableAbbrs:

  def __init__(self, *, schema:str, all_vis:Iterable[Vis]) -> None:
    self.schema_abbrs = TableAbbrs.abbreviate_schema_names({schema, *(vis.schema for vis in all_vis)})
    self.table_abbrs = Counter[str]()

  @staticmethod
  def abbreviate_schema_names(schema_names:set[str]) -> dict[str,str]:
    if len(schema_names) <= 1: return { n : '' for n in schema_names } # If only one schema is present then we can omit it entirely.
    tree = str_tree(sorted(schema_names))
    # We abbreviate by adding the first unique letter to each common prefix.
    return { prefix+suffix : prefix+suffix[:1] for prefix, suffix in str_tree_pairs(tree) }

  def simple_abbr(self, schema:str, table:str) -> str:
    'Generate a table abbreviation without concern for collision with other tables.'
    s = self.schema_abbrs[schema]
    t = capital_letters_abbr(table)
    return f'{s}{t}'

  def unique_abbr(self, schema:str, table:str) -> str:
    '''
    Generate a unique table abbreviation for use within the query.
    Where simple_abbr would collide with a previously issued abbreviation, adds a numer suffix.
    '''
    abbr = self.simple_abbr(schema, table)
    if n := self.table_abbrs[abbr]:
      abbrN = abbr + str(n)
    else: abbrN = abbr
    self.table_abbrs[abbr] += 1
    return abbrN



class Squelch:
  'An object that provides a web interface for running SQL queries.'

  def __init__(self,
    schemas:Iterable[Schema],
    vis: dict[str,dict[str,dict[str,Vis|bool]]], # Maps schema -> table -> column -> Vis|bool.
    order_by: dict[str,dict[str,str]]|None=None,
  ) -> None:

    self.schemas = { s.name : s for s in schemas }

    def _vis_for(schema:str, table:str, col:str) -> Vis:
      try: v = vis[schema][table][col]
      except KeyError: return Vis(show=True)
      else:
        if isinstance(v, Vis): return v
        elif isinstance(v, bool): return Vis(show=v)
        else: raise TypeError(f'invalid vis; schema={schema!r}, table={table!r}, col={col!r}; vis: {v!r}')

    self.vis:dict[str,dict[str,dict[str,Vis]]] = {
      s.name : { t.name : { c.name : _vis_for(s.name, t.name, c.name) for c in t.columns} for t in s.tables } for s in schemas }

    self.order_by:dict[str,dict[str,str]] = { s.name : {} for s in schemas }
    if order_by:
      for schema_name, schema_d in order_by.items():
        if schema_name not in self.order_by: raise ValueError(f'invalid `order_by` schema name: {schema_name!r}; valid names: {self.schemas.keys()}')
        schema = self.schemas[schema_name]
        for table_name, order_by_clause in schema_d.items():
          if table_name not in schema.tables_dict:
            raise ValueError(f'invalid `order_by` table name in schema {schema_name!r}: {table_name!r}; valid names: {schema.tables_dict.keys()}')
          self.order_by[schema_name][table_name] = order_by_clause


  def render(self, request:Request, conn:Conn) -> Div:
    '''
    Render a div representing the controls and optionally the DB query result from the request.
    '''
    path = request.url.path
    params = request.query_params

    if nst := self.get_schema_table(params):
      table_name, schema, table = nst
      table_vis = self.vis[schema.name][table.name]
      abbrs = TableAbbrs(schema=schema.name, all_vis=table_vis.values())

      # Enabled columns.
      en_col_names = set(
        [k[2:] for k in params if k.startswith('c-')]
        or [c.name for c in table.columns if table_vis[c.name].show]
        or [table.columns[0].name])

      en_col_spans = [
        Label(cl='en-col', _=[
          Input(name=f'c-{col.name}', type='checkbox', checked=Present(col.name in en_col_names)),
          col.name])
        for col in table.columns]

      order_by:str = params.get('order_by', '') or self.order_by[schema.name].get(table.name, '')

      if not order_by:
        if table.primary_key:
          order_by = '' # Use implied ordering for complex keys.
        elif primary_col := next((c for c in table.columns if c.is_primary), None):
          if primary_col.datatype == int: # Order by descending to see most recent rows first.
            order_by = f'{abbrs.unique_abbr(schema.name, table.name)}.{primary_col.name} DESC'

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

    div = Div(cl='squelch')

    div.append(squelch_ui_script())
    div.append(H1(A(href=path, _='SELECT')))

    form = div.append(Form(cl='kv-grid-max', action=path, autocomplete='off'))
    #^ autocomplete off is important for the table select input,
    #^ which otherwise remembers the current value when the user presses the back button.

    form.extend(
      Label('Table:'),
      Div(Select(name='table',
        onchange='emptyFirstForSelector("#columns"); resetValueForSelectorAll(".clear-on-table-change", "value"); this.form.submit()')
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
        self.render_table(conn=conn, schema=schema, table=table, abbrs=abbrs, path=path, params=params, en_col_names=en_col_names,
          order_by=order_by))

    title = 'Query'
    if table_name: title += f' {table_name}'
    if where := params.get('where'):
      title += f' WHERE {where}'
    return div


  def get_schema_table(self, params:QueryParams) -> tuple[str,Schema,Table]|None:

    try: full_name = params['table'] # The 'table' param is qualified and quoted, (e.g. 'schema.table' or '"some schema"."some table"').
    except KeyError: return None

    try: schema_name, table_name = sql_parse_schema_table(full_name)
    except ValueError as e: raise HTTPException(400, f'invalid table name: {full_name!r} ({e})')

    try: schema = self.schemas[schema_name]
    except KeyError: raise HTTPException(400, f'invalid schema: {schema_name!r}')

    try: table = schema.tables_dict[table_name]
    except KeyError: raise HTTPException(400, f'invalid table: {table_name!r}')

    return full_name, schema, table


  def render_table(self, *, conn:Conn, schema:Schema, table:Table, abbrs:TableAbbrs, path:str, params:QueryParams, en_col_names:set[str],
    order_by:str) -> list[HtmlNode]:

    assert en_col_names # Need at least one column to render.

    distinct = bool(params.get('distinct'))

    en_cols = [c for c in table.columns if c.name in en_col_names]

    where = params.get('where', '')

    limit = int(params.get('limit', 100) or 100)
    offset = int(params.get('offset', 0) or 0)

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
      plan = repr(tuple(c.run(f'EXPLAIN QUERY PLAN {query}').one()))
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
            if len(en_cols) == 1: count_query = f'SELECT COUNT(DISTINCT{columns_part}){from_clause}{where_clause}'
            else: count_query = f'SELECT COUNT() FROM (SELECT DISTINCT {columns_part}{from_clause}{where_clause})'
          else:
            count_query = f'SELECT COUNT(){from_clause}{where_clause}'
          count = c.run(count_query).one_col()
        except SqliteError as e:
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



def fmt_select_cols(schema:str, table:str, abbrs:TableAbbrs, path:str, cols:list[Column], table_vis:dict[str,Vis]
 ) -> tuple[str,str,list[Th],list[CellRenderFn]]:
  '''
  Return "[cols...]", "FROM/JOIN ...", the rendered table header names, and a list of render functions for each column.
  The columns string has a leading space.
  The from string has a leading newline.
  '''
  abbrs = TableAbbrs(schema=schema, all_vis=table_vis.values())
  t_abbr = abbrs.unique_abbr(schema, table) # Take the first, non-numbered abbreviation for the primary table.

  column_parts:list[str] = []
  line_len = 0
  def append_select_part(col_name:str):
    'Append a column name to the SELECT clause, wrapping lines as needed.'
    nonlocal line_len
    if column_parts:
      column_parts.append(',')
    if line_len + len(col_name) >= 128:
      column_parts.append('\n  ')
      line_len = 2
    else:
      column_parts.append(' ')
      line_len += 2
    column_parts.append(col_name)
    line_len += len(col_name)

  from_parts:list[str] = [f'\nFROM {qe(schema)}.{qe(table)} AS {t_abbr}']

  col_headers = []
  render_cell_fns:list[CellRenderFn] = []

  for col in cols:
    qcol = qe(col.name)
    qual_col = f'{t_abbr}.{qcol}'
    vis = table_vis[col.name]
    if vis.join:
      # Generate a join to show the desired visualization column.
      # We need to select two columns: the actual column value (for the tooltip and link), and the joined value for the visible text.
      join_table = abbrs.unique_abbr(vis.schema, vis.table)
      join_key = f'{join_table}.{qe(vis.join_col)}' # The joined table key.
      th = Th(Details(Summary(cl='disclosure-flush', _=qcol), f'{qe(vis.table)}.{qe(vis.col)}')) # The column header.
      join_col_name = f'{col.name}:{vis.schema}.{vis.table}.{vis.col}' # The join column needs a unique name.
      join_table_primary_abbr = abbrs.simple_abbr(vis.schema, vis.table)
      #^ The join table abbreviation when it is the primary table, for the WHERE clause in the link.
      append_select_part(qual_col) # The actual column value is needed to render the tooltip and link.
      append_select_part(f'{join_key} AS {qe(join_key)}') # The joined key lets us distinguish between no match and null joined value, because the key itself cannot be null.
      append_select_part(f'{join_table}.{qe(vis.col)} AS {qe(join_col_name)}') # The joined value.
      from_parts.append(f'\nLEFT JOIN {vis.schema_table} AS {join_table} ON {qual_col} = {join_key}')
      cell_fn = mk_cell_joined(col, vis, join_key, join_col_name, join_table_primary_abbr, app_path=path, render_fn=vis.render,
        renders_row=vis.renders_row)
    else:
      th = Th(col.name)
      append_select_part(qual_col)
      if vis.render:
        cell_fn = mk_cell_rendered(col, render_fn=vis.render, renders_row=vis.renders_row)
      else:
        cell_fn = mk_cell_plain(col)
    col_headers.append(th)
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


def mk_cell_joined(col:Column, vis:Vis, join_key:str, join_col_name:str, join_table_primary_abbr:str, app_path:str,
 render_fn:ValRenderFn|None, renders_row:bool) -> CellRenderFn:
  '''
  Create a cell value rendering function for the given column, with a join and possibly a custom render function.
  '''
  assert vis.join
  assert join_col_name
  assert join_table_primary_abbr

  q_join_col = f'{qe(join_table_primary_abbr)}.{qe(vis.join_col)}'

  def cell_joined(row:Row) -> Td:
    val = row[col.name]
    joined_key_val = row[join_key]
    if joined_key_val is None: # The join did not match.
      if val is None:
        return Td(cl='null unjoined', _='NULL')
      else:
        return Td(cl='unjoined', _=val)
    joined_val = row[join_col_name]
    if render_fn:
      cl, display_val = try_vis_render(render_fn, joined_val, row if renders_row else joined_val)
    elif joined_val is None:
      cl = 'null'
      display_val = 'NULL'
    elif joined_val == '':
      cl = 'empty'
      display_val = 'EMPTY'
    else:
      cl = ''
      display_val = str(joined_val)
    where = f'{q_join_col}={qv(val)}'
    return Td(cl=('joined', cl), _=A(href=fmt_url(app_path, table=vis.schema_table, where=where), title=val, _=display_val))

  return cell_joined


def try_vis_render(render_fn:ValRenderFn, val:Any, render_arg:Any) -> tuple[str,MuChild]:
  if val is None: return ('null', 'NULL')
  try:
    rendered = render_fn(render_arg)
    if not isinstance(rendered, MuChild): rendered = str(rendered)
    return ('', rendered)
  except Exception as e:
    warn(f'error rendering {val!r} with {render_fn}: {e}')
    return ('error', str(val))



def capital_letters_abbr(s:str) -> str:
  return ''.join(c for c in s if c.isupper())


def squelch_ui_script() -> Script:
  return Script('''
  function updateAllColCheckboxes(checked) {
    const checkboxes = document.querySelectorAll('.en-col input[type="checkbox"]');
    checkboxes.forEach(el => el.checked = checked);
  }
  ''')
