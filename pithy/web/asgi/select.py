# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from typing import Callable, Iterable, Sequence

from pithy.iterable import iter_interleave_sep
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
from ...sqlite.schema import Column, Schema, Table
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
        Span(cl='en-col', ch=[Input(name=f'c-{col.name}', type='checkbox', checked=Present(col.vis)), Label(ch=col.name)])
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
    except ValueError: raise HTTPException(400, f'invalid table name: {full_name!r}')

    try: schema = self.schemas[schema_name]
    except KeyError: raise HTTPException(400, f'invalid schema: {schema_name!r}')

    try: table = schema.tables_dict[table_name]
    except KeyError: raise HTTPException(400, f'invalid table: {table_name!r}')

    return full_name, schema, table


  def render_table(self, schema:Schema, table:Table, en_col_names:set[str], params:QueryParams) -> list[HtmlNode]:

    assert en_col_names # Need at least one column to render.

    distinct = bool(params.get('distinct'))

    en_cols = []
    for col_name in table.columns_dict:
      if col_name in en_col_names:
        en_cols.append(table.columns_dict[col_name])

    where = params.get('where', '')
    order_by = params.get('order_by', '')

    limit = int(params.get('limit', 100) or 100)

    select_clause = fmt_select_cols(en_cols, distinct=distinct)
    schema_table_sql = f'{qe(schema.name)}.{qe(table.name)}'
    order_by_clause = f'\nORDER BY {order_by}' if order_by else ''
    where_clause = f'\nWHERE {where}' if where else ''
    query = f'{select_clause}\nFROM {schema_table_sql}{where_clause}{order_by_clause}\nLIMIT {limit}'

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
        count = c.run(f"SELECT COUNT(1) FROM {schema_table_sql}{where_clause}").one_col()
      except Exception as e:
        count = f'Count failed: {e}\n{query}'
        is_ok = False

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
        Label(ch='Count:'), Pre(id='select_count', hx_swap_oob='innerHTML', ch=count and f'{count:,}'),
      ]),
      Div(id='results', ch=HtmlTable(cl='dense', ch=[
        Thead(ch=Tr(ch=[Th(ch=Div(ch=qe(col.name))) for col in en_cols])),
        Tbody(ch=rows)])),
    ]


def fmt_select_cols(cols:list[Column], distinct:bool) -> str:
  select = 'SELECT ' + ('DISTINCT ' if distinct else '')
  parts = [select]
  line_len = len(select)
  for i, col in enumerate(cols):
    qn = qe(col.name)
    if line_len + len(qn) >= 128:
      parts.append(',\n  ')
      line_len = 2
    elif i:
      parts.append(', ')
      line_len += 2
    parts.append(qn)
    line_len += len(qn)
  return ''.join(parts)
