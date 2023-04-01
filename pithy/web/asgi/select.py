# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter
from typing import Any, Callable, Iterable, Sequence

from pithy.iterable import iter_interleave_sep
from pithy.string import str_tree, str_tree_pairs
from pithy.url import fmt_url
from starlette.authentication import has_required_scope
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import QueryParams
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...html import (A, Div, Form, H1, HtmlNode, Input, Label, Main, MuChildLax, Pre, Present, Select, Span, Table as HtmlTable,
  Tbody, Td, Th, Thead, Tr)
from ...sqlite import Connection, Row
from ...sqlite.parse import sql_parse_schema_table
from ...sqlite.schema import Column, Schema, Table, Vis
from ...sqlite.util import sql_quote_entity as qe, sql_quote_val as qv


class SelectApp:
  'An ASGI app that provides a web interface for running SELECT queries.'

  def __init__(self, get_conn:Callable[[],Connection], html_response:Callable[[Request,Main],HTMLResponse],
   schemas:Iterable[Schema], requires:str|Sequence[str]=()) -> None:
    self.get_conn = get_conn
    self.html_response = html_response
    self.schemas = { s.name : s for s in schemas }
    self.requires = (requires,) if isinstance(requires, str) else tuple(requires)
    # TODO: optional table restrictions.


  async def __call__(self, scope, receive, send):
    'ASGI app interface.'
    request = Request(scope, receive)
    if not has_required_scope(request, self.requires): raise HTTPException(status_code=403)
    response = await run_in_threadpool(self.render_page, request)
    await response(scope, receive, send)


  def render_page(self, request:Request) -> HTMLResponse:
    '''
    The main page for the SELECT app.
    '''
    params = request.query_params

    if nst := self.get_schema_table(params):
      table_name, schema, table = nst

      en_col_names = set(
        [k[2:] for k in params if k.startswith('c-')]
        or [c.name for c in table.columns if (c.vis.show if isinstance(c.vis, Vis) else c.vis)]
        or [table.columns[0].name])

      en_col_spans = [
        Span(cl='en-col', ch=[
          Input(name=f'c-{col.name}', type='checkbox', checked=Present(col.name in en_col_names)),
          Label(ch=col.name)])
        for col in table.columns]

    else:
      table_name = ''
      schema = None
      en_col_names = set()
      en_col_spans = []

    table_names = [f'{qe(s.name)}.{qe(t.name)}' for s in self.schemas.values() for t in s.tables]
    if table_name: assert table_name in table_names
    main = Main(id='pithy_select_app', cl='bfull')

    main.append(H1(ch='SELECT'))

    form = main.append(Form(cl='kv-grid-max', action='./select', autocomplete='off'))
    #^ autocomplete off is important for the table select input,
    #^ which otherwise remembers the current value when the user presses the back button.

    form.extend(
      Label(ch='Table:'),
      Div(ch=Select.simple(name='table', placeholder='Table', value=table_name, options=table_names,
        onchange='emptyFirstForSelector("#columns"); clearValueAllForSelector(".clear-on-table-change", "value"); this.form.submit()')),

      Label(ch='Distinct:'),
      Div(ch=Input(name='distinct', type='checkbox', checked=Present(params.get('distinct')))),

      Label(ch='Columns:'),
      Div(id='columns', ch=iter_interleave_sep(en_col_spans, ' '), cl='clear-on-table-change'),

      Label(ch='Where:'),
      Input(name='where', type='text', value=params.get('where', ''), cl='clear-on-table-change'),

      Label(ch='Order by:'),
      Input(name='order_by', type='text', value=params.get('order_by', ''),  cl='clear-on-table-change'),

      Label(ch='Limit:'),
      Div(ch=Input(name='limit', type='number', value=params.get('limit', '100'), cl='clear-on-table-change')),

      Label(),
      Div(ch=Input(type='submit', value='Run Query')),
    )

    if table_name:
      assert schema
      main.extend(self.render_table(schema, table, en_col_names, request.query_params))

    return self.html_response(request, main)


  def get_schema_table(self, params:QueryParams) -> tuple[str,Schema,Table]|None:

    try: full_name = params['table']
    except KeyError: return None

    try: schema_name, table_name = sql_parse_schema_table(full_name)
    except ValueError as e: raise HTTPException(400, f'invalid table name: {full_name!r} ({e})')

    try: schema = self.schemas[schema_name]
    except KeyError: raise HTTPException(400, f'invalid schema: {schema_name!r}')

    try: table = schema.tables_dict[table_name]
    except KeyError: raise HTTPException(400, f'invalid table: {table_name!r}')

    return full_name, schema, table


  def render_table(self, schema:Schema, table:Table, en_col_names:set[str], params:QueryParams) -> list[HtmlNode]:

    assert en_col_names # Need at least one column to render.

    distinct = bool(params.get('distinct'))

    en_cols = [c for c in table.columns if c.name in en_col_names]

    where = params.get('where', '')
    order_by = params.get('order_by', '')

    limit = int(params.get('limit', 100) or 100)

    columns_part, from_clause, header_names, render_cell_fns = fmt_select_cols(
      schema=schema.name, table=table.name, cols=en_cols)

    select_head = 'SELECT' + (' DISTINCT' if distinct else '')
    where_clause = f'\nWHERE {where}' if where else ''
    order_by_clause = f'\nORDER BY {order_by}' if order_by else ''

    query = f'{select_head}{columns_part}{from_clause}{where_clause}{order_by_clause}\nLIMIT {limit}'

    conn = self.get_conn()
    c = conn.cursor()
    try:
      plan = repr(tuple(c.run(f'EXPLAIN QUERY PLAN {query}').one()))
      is_ok = True
    except Exception as e:
      plan = f'Explain query failed: {e}\n{query}'
      is_ok = False

    count = ''
    if is_ok:
      try:
        count_int = c.run(f'SELECT COUNT() {from_clause}{where_clause}').one_col()
      except Exception as e:
        count = f'Count failed: {e}\n{query}'
      else:
        count = f'{count_int:,}'

    rows = []
    if is_ok:
      try: c = c.run(query)
      except Exception as e:
        plan = f'Query failed: {e}\n{query}'
        is_ok = False
      else:
        rows = [Tr(ch=[Td(ch=rcf(row)) for rcf in render_cell_fns]) for row in c]

    return [
      Div(id='query', cl='kv-grid-max', ch=[
        Label(ch='Query:'), Pre(id='select_query', hx_swap_oob='innerHTML', ch=query),
        Label(ch='Plan:'), Pre(id='select_plan', hx_swap_oob='innerHTML', ch=plan),
        Label(ch='Count:'), Pre(id='select_count', hx_swap_oob='innerHTML', ch=count and f'{count}'),
      ]),
      Div(id='results', ch=HtmlTable(cl='dense', ch=[
        Thead(ch=Tr(ch=[Th(ch=Div(ch=name)) for name in header_names])),
        Tbody(ch=rows)])),
    ]


CellRenderFn = Callable[[Any],MuChildLax]


def fmt_select_cols(schema:str, table:str, cols:list[Column]) -> tuple[str,str,list[str],list[CellRenderFn]]:
  '''
  Return "SELECT [cols...]", "FROM/JOIN ...", the rendered table header names, and a list of render functions for each column.
  '''

  all_vis = [col.vis for col in cols if isinstance(col.vis, Vis)]
  schema_abbrs = abbreviate_schema_names({schema, *(vis.schema for vis in all_vis)})
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

  for i, col in enumerate(cols):
    qcol = qe(col.name)
    qual_col = f'{t_abbr}.{qcol}'
    vis = col.vis
    if isinstance(vis, Vis) and vis.join:
      # Generate a join to show the desired visualization column.
      # We need to select two columns, rendered cell value and the actual column value for the link to the joined table.
      vis_t = table_abbr(vis.schema, vis.table)
      head_name = f'{col.name}: {vis.table}.{vis.col}'
      join_col_name = f'{col.name}:{vis.schema}.{vis.table}.{vis.col}' # The join column needs a unique name.
      join_table_primary_abbr = simple_table_abbr(vis.schema, vis.table) # The join table abbrev when it is the primary table.
      append_select_part(f'COALESCE({vis_t}.{qe(vis.col)}, {qual_col}) AS {qe(join_col_name)}') # The joined value.
      append_select_part(qual_col) # The actual column value is also needed to render the hyperlink.
      from_parts.append(f'\nLEFT JOIN {vis.schema_table} AS {vis_t} ON {qual_col} = {vis_t}.{qe(vis.join_col)}')
    else:
      head_name = qe(col.name)
      join_col_name = ''
      join_table_primary_abbr = ''
      append_select_part(qual_col)
    header_names.append(head_name)
    render_cell_fns.append(mk_render_cell_fn(col, join_col_name=join_col_name, join_table_primary_abbr=join_table_primary_abbr))

  return ''.join(column_parts), ''.join(from_parts), header_names, render_cell_fns


def mk_render_cell_fn(col:Column, join_col_name:str, join_table_primary_abbr:str) -> CellRenderFn:
  'Create a cell function a column in the rendered output.'

  if isinstance(col.vis, Vis):
    def render_cell_vis(row:Row) -> MuChildLax:
      vis = col.vis
      assert isinstance(vis, Vis)
      assert join_col_name
      assert join_table_primary_abbr
      val = row[col.name]
      join_val = row[join_col_name]
      if vis.join:
        where = f'{qe(join_table_primary_abbr)}.{qe(vis.join_col)}={qv(val)}'
        return A(href=fmt_url('./select', table=vis.schema_table, where=where), ch=render_val_plain(join_val))
      return render_val_plain(val)
    return render_cell_vis

  else:
    def render_cell_plain(row:Row) -> MuChildLax:
      val = row[col.name]
      if val is None: return Span(cl='null', ch='NULL')
      return A.maybe(str(val))
    return render_cell_plain


def render_val_plain(val:Any) -> MuChildLax:
  if val is None: return Span(cl='null', ch='NULL')
  return A.maybe(str(val))


def abbreviate_schema_names(schema_names:set[str]) -> dict[str,str]:
  if len(schema_names) < 2: return { n : '' for n in schema_names } # If only one schema is present then we can omit it entirely.
  tree = str_tree(sorted(schema_names))
  return { prefix+suffix : prefix+suffix[:1] for prefix, suffix in str_tree_pairs(tree) }


def capital_letters_abbr(s:str) -> str:
  return ''.join(c for c in s if c.isupper())
