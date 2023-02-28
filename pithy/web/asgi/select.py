# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from typing import Callable, Iterable, Sequence

from starlette.authentication import has_required_scope
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Mount

from ...html import Div, Form, H1, Input, Label, Main, Pre, Present, Select, Span, Table as HtmlTable, Tbody, Td, Th, Thead, Tr
from ...sqlite import Connection
from ...sqlite.parse import sql_parse_schema_table
from ...sqlite.schema import Column, Schema, Table
from ...sqlite.util import sql_quote_entity as qe
from ..starlette import htmx_response


class SelectApp:
  'An ASGI app that provides a web interface for running SELECT queries.'

  def __init__(self, path:str, get_conn:Callable[[],Connection], html_response:Callable[[Request,Main],HTMLResponse],
   schemas:Iterable[Schema], requires:str|Sequence[str]=()) -> None:
    if path.endswith('/'): raise ValueError(f'SelectApp mount path must not end with slash: {path!r}')
    self.path = path
    self.get_conn = get_conn
    self.html_response = html_response
    self.schemas = { s.name : s for s in schemas }
    self.requires = (requires,) if isinstance(requires, str) else tuple(requires)
    # TODO: optional table restrictions.


  def mount(self) -> Mount: return Mount(self.path, self)


  async def __call__(self, scope, receive, send):
    'ASGI app interface.'
    request = Request(scope, receive)
    if not has_required_scope(request, self.requires): raise HTTPException(status_code=403)
    response = await self.dispatch(request)
    await response(scope, receive, send)


  async def dispatch(self, request:Request) -> HTMLResponse:
    whole_path = request.url.path
    assert whole_path.startswith(self.path)
    rel_path = whole_path.removeprefix(self.path)
    match rel_path:
      case '/':
        return self.select_index(request)
      case '/select_setup.htmx':
        return self.select_setup_htmx(request)
      case '/select_query.htmx':
        return self.select_query_htmx(request)
      case _: raise HTTPException(404)


  def select_index(self, request:Request) -> HTMLResponse:

    conn = self.get_conn()
    c = conn.cursor()

    table_names = [f'{qe(schema.name)}.{qe(table.name)}'
      for schema in self.schemas.values()
      for table in schema.tables]

    main = Main(id='pithy_select_app', cl='bfull')

    main.append(H1(ch='SELECT'))
    form = main.append(Form(id='select_form'))

    form.extend(
      Label(ch='Table:'),
      Select.simple(name='table', placeholder='Table', options=table_names,
        hx_trigger='change',
        hx_get='./select_setup.htmx',
        hx_target='#select_columns'),

      Label(ch='Distinct:'),
      Input(name='distinct', type='checkbox'),

      Label(ch='Columns:'),
      Div(id='select_columns'),

      Label(ch='Where:'),
      Input(name='where', type='text'),

      Label(ch='Order by:'),
      Input(name='order_by', type='text'),

      Label(ch='Limit:'),
      Input(name='limit', type='number', value='100'),

      Label(ch=''),
      Input(type='submit', value='Run Query',
        hx_trigger='click',
        hx_get='./select_query.htmx',
        hx_include='#select_form',
        hx_target='#select_results'),

      Label(ch='Query:'),
      Pre(id='select_query', cl='empty-on-form-change'),

      Label(ch='Plan:'),
      Pre(id='select_plan', cl='empty-on-form-change'),

      Label(ch='Count:'),
      Pre(id='select_count', cl='empty-on-form-change'),
    )

    results_div = main.append(Div(cl='bleed-content', style='overflow-x:auto'))
    results_div.append(HtmlTable(id='select_results', cl='empty-on-form-change dense'))

    return self.html_response(request, main)


  def get_schema_and_table(self, request:Request) -> tuple[Schema,Table]:
    params = request.query_params

    try: schema_table = params['table']
    except KeyError: raise HTTPException(400, "missing parameter: 'table'")

    schema_name, table_name = sql_parse_schema_table(schema_table)
    try: schema = self.schemas[schema_name]
    except KeyError: raise HTTPException(400, f'invalid schema: {schema_name!r}')

    try: table = schema.tables_dict[table_name]
    except KeyError: raise HTTPException(400, f'invalid table: {table_name!r}')

    return schema, table


  def select_setup_htmx(self, request:Request) -> HTMLResponse:
    schema, table = self.get_schema_and_table(request)

    spans = [
      Span(cl='enable-column', ch=[Input(type='checkbox', name=f'c-{col.name}', checked=Present(col.vis)), Label(ch=col.name)])
      for col in table.columns]

    return htmx_response(*spans,
      Div(hx_swap_oob='innerHTML:.empty-on-form-change'),
    )


  def select_query_htmx(self, request:Request) -> HTMLResponse:
    schema, table = self.get_schema_and_table(request)

    params = request.query_params

    distinct = bool(params.get('distinct'))
    en_col_names = [k[2:] for k in params if k.startswith('c-')]

    en_cols = []
    for col_name in en_col_names:
      if col_name not in table.columns_dict:
        raise HTTPException(400, f'invalid column: {col_name!r}')
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

    return htmx_response(
      Thead(ch=Tr(ch=[Th(ch=Div(ch=qe(col.name))) for col in en_cols])),
      Tbody(ch=rows),
      Pre(id='select_query', hx_swap_oob='innerHTML', ch=query),
      Pre(id='select_plan', hx_swap_oob='innerHTML', ch=plan),
      Pre(id='select_count', hx_swap_oob='innerHTML', ch=count and f'{count:,}'),
    )


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
