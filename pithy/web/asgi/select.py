# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter
from typing import Any, Callable, cast, Iterable, Sequence
from warnings import warn

from pithy.string import str_tree, str_tree_pairs
from pithy.url import fmt_url
from starlette.authentication import has_required_scope
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import QueryParams
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...html import (A, Div, Form, H1, HtmlNode, Input, Label, Main, MuChild, Pre, Present, Script, Select, Span,
  Table as HtmlTable, Tbody, Td, Th, Thead, Tr)
from ...html.parse import linkify
from ...html.parts import pagination_control
from ...sqlite import Connection, Row, SqliteError
from ...sqlite.parse import sql_parse_schema_table
from ...sqlite.schema import Column, Schema, Table
from ...sqlite.util import sql_quote_entity as qe, sql_quote_val as qv
from .vis import Vis


ValRenderFn = Callable[[Any],Any]
CellRenderFn = Callable[[Any],Td]


class SelectApp:
  'An ASGI app that provides a web interface for running SELECT queries.'

  def __init__(self,
    get_conn:Callable[[],Connection],
    html_response:Callable[[Request,Main],HTMLResponse],
    schemas:Iterable[Schema],
    vis: dict[str,dict[str,dict[str,Vis|bool]]], # Maps schema -> table -> column -> Vis|bool.
    order_by: dict[str,dict[str,str]]|None=None,
    requires:str|Sequence[str]=()
  ) -> None:

    self.get_conn = get_conn
    self.html_response = html_response
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

    self.requires = (requires,) if isinstance(requires, str) else tuple(requires)
    # TODO: optional table restrictions.


  async def __call__(self, scope, receive, send):
    'ASGI app interface.'
    request = Request(scope, receive)
    if not has_required_scope(request, self.requires): raise HTTPException(status_code=403)
    response = await run_in_threadpool(self.render_page, request)
    await response(scope, receive, send)


  def should_show(self, schema:str, table:str, col:str) -> bool:
    try: return self.vis[schema][table][col].show
    except KeyError: return True


  def render_page(self, request:Request) -> HTMLResponse:
    '''
    The main page for the SELECT app.
    '''
    params = request.query_params

    if nst := self.get_schema_table(params):
      table_name, schema, table = nst
      table_vis = self.vis[schema.name][table.name]

      en_col_names = set(
        [k[2:] for k in params if k.startswith('c-')]
        or [c.name for c in table.columns if table_vis[c.name].show]
        or [table.columns[0].name])

      en_col_spans = [
        Span(cl='en-col', _=[
          Input(name=f'c-{col.name}', type='checkbox', checked=Present(col.name in en_col_names)),
          Label(col.name)])
        for col in table.columns]

      order_by = params.get('order_by', '') or self.order_by[schema.name].get(table.name, '')

    else:
      table_name = ''
      schema = None
      table = None
      en_col_names = set()
      en_col_spans = []
      order_by = ''

    table_names = [f'{qe(s.name)}.{qe(t.name)}' for s in self.schemas.values() for t in s.tables]
    if table_name: assert table_name in table_names # Sanity check that these generated table names match the parsed table name.

    main = Main(id='pithy_select_app', cl='bfull')

    main.append(main_script())
    main.append(H1('SELECT'))

    form = main.append(Form(cl='kv-grid-max', action='./select', autocomplete='off'))
    #^ autocomplete off is important for the table select input,
    #^ which otherwise remembers the current value when the user presses the back button.

    form.extend(
      Label('Table:'),
      Div(Select.simple(name='table', placeholder='Table', value=table_name, options=table_names,
        onchange='emptyFirstForSelector("#columns"); resetValueForSelectorAll(".clear-on-table-change", "value"); this.form.submit()')),

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
      main.extend(self.render_table(schema, table, en_col_names, order_by, request.query_params))

    return self.html_response(request, main)


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


  def render_table(self, schema:Schema, table:Table, en_col_names:set[str], order_by:str, params:QueryParams) -> list[HtmlNode]:

    assert en_col_names # Need at least one column to render.

    distinct = bool(params.get('distinct'))

    en_cols = [c for c in table.columns if c.name in en_col_names]

    where = params.get('where', '')

    limit = int(params.get('limit', 100) or 100)
    offset = int(params.get('offset', 0) or 0)

    table_vis = self.vis[schema.name][table.name]

    columns_part, from_clause, header_names, render_cell_fns = fmt_select_cols(
      schema=schema.name, table=table.name, cols=en_cols, table_vis=table_vis)

    select_head = 'SELECT' + (' DISTINCT' if distinct else '')
    where_clause = f'\nWHERE {where}' if where else ''
    order_by_clause = f'\nORDER BY {order_by}' if order_by else ''

    query = f'{select_head}{columns_part}{from_clause}{where_clause}{order_by_clause}\nLIMIT {limit} OFFSET {offset}'

    conn = self.get_conn()
    c = conn.cursor()
    try:
      plan = repr(tuple(c.run(f'EXPLAIN QUERY PLAN {query}').one()))
      is_ok = True
    except Exception as e:
      plan = f'Explain query failed: {e}\n{query}'
      is_ok = False

    count:int|None = None
    if is_ok:
      try:
        count = c.run(f'{select_head} COUNT() {from_clause}{where_clause}').one_col()
      except SqliteError as e:
        is_ok = False

    rows = []
    if is_ok:
      try: c = c.run(query)
      except Exception as e:
        plan = f'Query failed: {e}\n{query}'
        is_ok = False
      else:
        rows = [Tr(_=[rcf(row) for rcf in render_cell_fns]) for row in c]

    return [
      Div(id='query', cl='kv-grid-max', _=[
        Label('Query:'), Pre(id='select_query', hx_swap_oob='innerHTML', _=query),
        Label('Plan:'), Pre(id='select_plan', hx_swap_oob='innerHTML', _=plan),
      ]),
      Div(id='pagination', cl='kv-grid-max',  _=[pagination_control(count, limit, offset, params)]),
      Div(id='results', _=HtmlTable(cl='dense', _=[
        Thead(Tr(_=[Th(Div(name)) for name in header_names])),
        Tbody(_=rows)])),
    ]


def fmt_select_cols(schema:str, table:str, cols:list[Column], table_vis:dict[str,Vis]) -> tuple[str,str,list[str],list[CellRenderFn]]:
  '''
  Return "SELECT [cols...]", "FROM/JOIN ...", the rendered table header names, and a list of render functions for each column.
  '''

  schema_abbrs = abbreviate_schema_names({schema, *(vis.schema for vis in table_vis.values())})
  table_abbrs = Counter[str]()

  def simple_table_abbr(schema:str, table:str) -> str:
    'Generate a table abbreviation without concern for collision with other tables.'
    s = schema_abbrs[schema]
    t = capital_letters_abbr(table)
    return f'{s}{t}'

  def table_abbr(schema:str, table:str) -> str:
    'Generate a unique table abbreviation for use within the query.'
    abbr = simple_table_abbr(schema, table)
    if n := table_abbrs[abbr]: abbrN = abbr + str(n)
    else: abbrN = abbr
    table_abbrs[abbr] += 1
    return abbrN

  t_abbr = table_abbr(schema, table)

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

  header_names = []
  render_cell_fns:list[CellRenderFn] = []

  for col in cols:
    qcol = qe(col.name)
    qual_col = f'{t_abbr}.{qcol}'
    vis = table_vis[col.name]
    if vis.join:
      # Generate a join to show the desired visualization column.
      # We need to select two columns: the actual column value (for the tooltip and link), and the joined value for the visible text.
      join_table = table_abbr(vis.schema, vis.table)
      join_key = f'{join_table}.{qe(vis.join_col)}' # The joined table key.
      head_name = f'{col.name}: {vis.table}.{vis.col}' # The column header name.
      join_col_name = f'{col.name}:{vis.schema}.{vis.table}.{vis.col}' # The join column needs a unique name.
      join_table_primary_abbr = simple_table_abbr(vis.schema, vis.table) # The join table abbrev when it is the primary table, for the link WHERE clause.
      append_select_part(qual_col) # The actual column value is needed to render the tooltip and link.
      append_select_part(f'{join_key} AS {qe(join_key)}') # The joined key lets us distinguish between no match and null joined value, because the key itself cannot be null.
      append_select_part(f'{join_table}.{qe(vis.col)} AS {qe(join_col_name)}') # The joined value.
      from_parts.append(f'\nLEFT JOIN {vis.schema_table} AS {join_table} ON {qual_col} = {join_key}')
      cell_fn = mk_cell_joined(col, vis, join_key, join_col_name, join_table_primary_abbr, render_fn=vis.render)
    else:
      head_name = qe(col.name)
      append_select_part(qual_col)
      if vis.render:
        cell_fn = mk_cell_rendered(col, render_fn=vis.render)
      else:
        cell_fn = mk_cell_plain(col)
    header_names.append(head_name)
    render_cell_fns.append(cell_fn)

  return ''.join(column_parts), ''.join(from_parts), header_names, render_cell_fns


def mk_cell_plain(col:Column) -> CellRenderFn:
  '''
  Create a cell value rendering function for the given column, with no join or render customization.
  '''
  def cell_plain(row:Row) -> Td:
    val = row[col.name]
    if val is None: return Td(cl='null', _='NULL')
    return Td(_=linkify(str(val)))

  return cell_plain


def mk_cell_rendered(col:Column, render_fn:ValRenderFn) -> CellRenderFn:
  '''
  Create a cell value rendering function for the given column, with no join but a custom render function.
  '''
  def cell_rendered(row:Row) -> Td:
    val = row[col.name]
    cl, display_val = try_vis_render(render_fn, val)
    return Td(cl=cl, _=display_val)

  return cell_rendered


def mk_cell_joined(col:Column, vis:Vis, join_key:str, join_col_name:str, join_table_primary_abbr:str, render_fn:ValRenderFn|None) -> CellRenderFn:
  '''
  Create a cell value rendering function for the given column, with a join and possibly a custom render function.
  '''
  assert vis.join

  def cell_joined(row:Row) -> Td:
    assert join_col_name
    assert join_table_primary_abbr
    val = row[col.name]
    joined_key_val = row[join_key]
    if joined_key_val is None: # The join did not match.
      if val is None:
        return Td(cl='null unjoined', _='NULL')
      else:
        return Td(cl='unjoined', _=val)
    joined_val = row[join_col_name]
    if render_fn:
      cl, display_val = try_vis_render(render_fn, joined_val)
    elif joined_val is None:
      cl = 'null'
      display_val = 'NULL'
    else:
      cl = ''
      display_val = str(joined_val)
    where = f'{qe(join_table_primary_abbr)}.{qe(vis.join_col)}={qv(val)}'
    return Td(cl=('joined', cl), _=A(href=fmt_url('./select', table=vis.schema_table, where=where), title=val, _=display_val))

  return cell_joined


def try_vis_render(render_fn:ValRenderFn, val:Any) -> tuple[str,MuChild]:
  if val is None: return ('null', 'NULL')
  try:
    rendered = render_fn(val)
    if not isinstance(rendered, MuChild): rendered = str(rendered) # type: ignore[misc, arg-type]
    return ('', rendered)
  except Exception as e:
    warn(f'error rendering {val!r} with {render_fn}: {e}')
    return ('error', str(val))


def abbreviate_schema_names(schema_names:set[str]) -> dict[str,str]:
  if len(schema_names) < 2: return { n : '' for n in schema_names } # If only one schema is present then we can omit it entirely.
  tree = str_tree(sorted(schema_names))
  return { prefix+suffix : prefix+suffix[:1] for prefix, suffix in str_tree_pairs(tree) }


def capital_letters_abbr(s:str) -> str:
  return ''.join(c for c in s if c.isupper())


def main_script() -> Script:
  return Script('''
  function updateAllColCheckboxes(checked) {
    const checkboxes = document.querySelectorAll('span.en-col input[type="checkbox"]');
    checkboxes.forEach(el => el.checked = checked);
  }
  ''')
