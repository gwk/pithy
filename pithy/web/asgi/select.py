# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections import Counter
from typing import Callable, Iterable, Sequence

from pithy.io import outM
from pithy.iterable import iter_interleave_sep
from pithy.string import str_tree, str_tree_iter, str_tree_pairs
from starlette.authentication import has_required_scope
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import QueryParams
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse

from ...html import (Div, Form, H1, HtmlNode, Input, Label, Main, Pre, Present, Select, Span, Table as HtmlTable, Tbody, Td, Th,
  Thead, Tr)
from ...sqlite import Connection
from ...sqlite.parse import sql_parse_schema_table
from ...sqlite.schema import Column, Schema, Table, Vis
from ...sqlite.util import sql_quote_entity as qe


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
        [k[2:] for k in params if k.startswith('c-')] or [c.name for c in table.columns if c.vis] or [table.columns[0].name])

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

    form = main.append(Form(cl='kv-grid', action='./select'))

    form.extend(
      Label(ch='Table:'),
      Select.simple(name='table', placeholder='Table', value=table_name, options=table_names,
        onchange='emptyFirstForSelector("#columns"); clearValueAllForSelector(".clear-on-table-change", "value"); this.form.submit()'),

      Label(ch='Distinct:'),
      Input(name='distinct', type='checkbox', checked=Present(params.get('distinct'))),

      Label(ch='Columns:'),
      Div(id='columns', ch=iter_interleave_sep(en_col_spans, ' '), cl='clear-on-table-change'),

      Label(ch='Where:'),
      Input(name='where', type='text', value=params.get('where', ''), cl='clear-on-table-change'),

      Label(ch='Order by:'),
      Input(name='order_by', type='text', value=params.get('order_by', ''),  cl='clear-on-table-change'),

      Label(ch='Limit:'),
      Input(name='limit', type='number', value=params.get('limit', '100'), cl='clear-on-table-change'),

      Label(ch=''),
      Input(type='submit', value='Run Query'),
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

    header_names, select_clause, from_clause = fmt_select_cols(schema=schema.name, table=table.name, cols=en_cols, distinct=distinct)
    where_clause = f'\nWHERE {where}' if where else ''
    order_by_clause = f'\nORDER BY {order_by}' if order_by else ''
    query = f'{select_clause}{from_clause}{where_clause}{order_by_clause}\nLIMIT {limit}'

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
        count_int = c.run(f"SELECT COUNT(1) {from_clause}{where_clause}").one_col()
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
        rows = [Tr(ch=[Td(ch=cell) for cell in row]) for row in c]

    return [
      Div(id='query', cl='kv-grid', ch=[
        Label(ch='Query:'), Pre(id='select_query', hx_swap_oob='innerHTML', ch=query),
        Label(ch='Plan:'), Pre(id='select_plan', hx_swap_oob='innerHTML', ch=plan),
        Label(ch='Count:'), Pre(id='select_count', hx_swap_oob='innerHTML', ch=count and f'{count}'),
      ]),
      Div(id='results', ch=HtmlTable(cl='dense', ch=[
        Thead(ch=Tr(ch=[Th(ch=Div(ch=name)) for name in header_names])),
        Tbody(ch=rows)])),
    ]


def fmt_select_cols(schema:str, table:str, cols:list[Column], distinct:bool) -> tuple[list[str],str,str]:
  '''
  Return the rendered table header names, the SELECT [cols...] portion, and FROM/JOIN portion of the query.
  '''
  all_vis = [col.vis for col in cols if isinstance(col.vis, Vis)]
  schema_abbrs = abbreviate_schema_names({schema, *(vis.schema for vis in all_vis)})
  table_abbrs = Counter[str]()

  def table_abbr(schema:str, table:str) -> str:
    s = schema_abbrs[schema]
    t = capital_letters_abbr(table)
    abbr = f'{s}{t}'
    if n := table_abbrs[abbr]: abbrN = abbr + str(n)
    else: abbrN = abbr
    table_abbrs[abbr] += 1
    return abbrN

  t_abbr = table_abbr(schema, table)

  select = 'SELECT ' + ('DISTINCT ' if distinct else '')
  header_names = []
  select_parts = [select]
  from_parts:list[str] = [f'\nFROM {qe(schema)}.{qe(table)} AS {t_abbr}']
  line_len = len(select)

  for i, col in enumerate(cols):
    vis = col.vis
    if isinstance(vis, Vis) and vis.join:
      # Generate a join to show the desired visualization column.
      vis_t = table_abbr(vis.schema, vis.table)
      qual_col = f'{t_abbr}.{qe(col.name)}'
      col_name = f'COALESCE({vis_t}.{qe(vis.col)}, {qual_col})'
      head_name = f'{col.name}: {vis_t}.{vis.col}'
      from_parts.append(f'\nLEFT JOIN {vis.schema_table} AS {vis_t} ON {qual_col} = {vis_t}.{qe(vis.join_col)}')
    else:
      col_name = f'{t_abbr}.{qe(col.name)}'
      head_name = qe(col.name)
    if i:
      if line_len + len(col_name) >= 128:
        select_parts.append(',\n  ')
        line_len = 2
      else:
        select_parts.append(', ')
        line_len += 2
    header_names.append(head_name)
    select_parts.append(col_name)
    line_len += len(col_name)

  return header_names, ''.join(select_parts), ''.join(from_parts)


def abbreviate_schema_names(schema_names:set[str]) -> dict[str,str]:
  if len(schema_names) < 2: return { n : '' for n in schema_names } # If only one schema is present then we can omit it entirely.
  tree = str_tree(sorted(schema_names))
  return { prefix+suffix : prefix+suffix[:1] for prefix, suffix in str_tree_pairs(tree) }


def capital_letters_abbr(s:str) -> str:
  return ''.join(c for c in s if c.isupper())
