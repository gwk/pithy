# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from copy import deepcopy
from json import dumps
from unittest.mock import Mock

from pithy.json import JsonDict
from pithy.secrets import SecretStr
from requests import Response, Session
from tap_betterstack.client import api_url, BetterStackError, Client
from tap_betterstack.dashboards import push_dashboard
from tap_betterstack.metrics import push_metrics
from tap_betterstack.models import (Chart, ChartSpec, Dashboard, DashboardDefinition, DashboardSpec, MetricSpec, Query,
  SectionSpec, Variable)
from utest import utest_exc, utest_run, utest_val


dashboard_data:JsonDict = {
  'id': '1234', 'type': 'dashboard', 'attributes': {
    'team_id': 1, 'team_name': 'My Team', 'name': 'Overview', 'dashboard_group_id': None,
    'refresh_interval': 60, 'date_range_from': 'now-3h', 'date_range_to': 'now',
    'created_at': '2026-01-01T00:00:00.000Z', 'updated_at': '2026-01-01T00:00:00.000Z',
    'future_field': True}}
chart_data:JsonDict = {
  'id': '567', 'type': 'chart', 'attributes': {
    'chart_type': 'line_chart', 'name': 'Events', 'description': None, 'x': 0, 'y': 0, 'w': 6, 'h': 4,
    'settings': {'nested': {'null_value': None}},
    'queries': [{'id': 890, 'name': None, 'query_type': 'sql_expression', 'source_variable': 'source',
      'sql_query': 'SELECT 1'}]}}


def response(body:JsonDict, status:int=200) -> Response:
  result = Response()
  result.status_code = status
  result._content = dumps(body).encode()
  result._content_consumed = True
  return result


def fake_client(*responses:Response) -> tuple[Client,Mock]:
  session = Session()
  request = Mock(side_effect=responses)
  session.request = request # type: ignore[method-assign]
  return Client(SecretStr('test-token'), team_name='My Team', session=session), request


@utest_run
def models() -> None:
  dashboard = Dashboard.from_json(dashboard_data)
  utest_val(None, dashboard.attributes.charts)
  utest_val(None, dashboard.attributes.dashboard_group_id)
  chart = Chart.from_json(chart_data)
  utest_val(890, chart.attributes.queries[0].id)
  utest_val({'query_type': 'sql_expression', 'source_variable': 'source',
    'sql_query': 'SELECT 1'}, chart.attributes.queries[0].as_json())
  utest_val({'nested': {'null_value': None}}, chart.attributes.as_json()['settings'])
  utest_val({'name': 'source', 'variable_type': 'source', 'values': [], 'default_values': [],
    'allow_multiple_values': False}, Variable(name='source', variable_type='source', allow_multiple_values=False).as_json())
  utest_val(0, DashboardSpec(name='Empty').as_json()['refresh_interval'])
  # Fetched attributes serialize as a request spec: response-only fields are omitted.
  utest_val({'name': 'Overview', 'refresh_interval': 60, 'date_range_from': 'now-3h', 'date_range_to': 'now'},
    dashboard.attributes.as_json())
  malformed = deepcopy(dashboard_data)
  del malformed['attributes']
  utest_exc(Exception, Dashboard.from_json, malformed)


@utest_run
def pagination() -> None:
  client, request = fake_client(
    response({'data': [dashboard_data], 'pagination': {'next': 'https://untrusted.example/page2'}}),
    response({'data': [dashboard_data], 'pagination': {'next': None}}))
  utest_val(2, len(list(client.iter_dashboards(query='Overview'))))
  utest_val([1, 2], [call.kwargs['params']['page'] for call in request.call_args_list])
  for call in request.call_args_list:
    utest_val(('GET', api_url + '/dashboards'), call.args)
    utest_val('Bearer test-token', call.kwargs['headers']['Authorization'])
    utest_val(False, call.kwargs['allow_redirects'])
    utest_val(30, call.kwargs['timeout'])


@utest_run
def writes_and_errors() -> None:
  client, request = fake_client(response({'data': dashboard_data}), response({'data': dashboard_data}), response({}, 204))
  client.create_dashboard(DashboardSpec(name='Overview'))
  utest_val('My Team', request.call_args.kwargs['json']['team_name'])
  client.update_dashboard('1234', {'dashboard_group_id': None, 'variables': []})
  utest_val({'dashboard_group_id': None, 'variables': []}, request.call_args.kwargs['json'])
  client.delete_dashboard('1234')
  utest_val('DELETE', request.call_args.args[0])
  for status in (401, 404, 422, 429, 500, 302):
    result = response({'errors': 'Rejected'}, status)
    result.headers['Retry-After'] = '60'
    client, request = fake_client(result)
    try: client.create_dashboard(DashboardSpec(name='Overview'))
    except BetterStackError as e:
      utest_val(status, e.status)
      utest_val({'errors': 'Rejected'}, e.body)
      utest_val('60', e.retry_after)
    else: raise AssertionError('Expected an API error.')
    utest_val(1, request.call_count)


@utest_run
def export_import() -> None:
  exported:JsonDict = {'name': 'Exported', 'preset': {}, 'charts': [{'chart_queries': []}]}
  client, request = fake_client(response({'id': 1234, 'name': 'Exported', 'data': exported}),
    response({'data': dashboard_data}))
  client.import_dashboard(client.export_dashboard('1234'))
  utest_val({'data': exported, 'team_name': 'My Team'}, request.call_args.kwargs['json'])


@utest_run
def repeat_push() -> None:
  definition = DashboardDefinition(dashboard=DashboardSpec(name='Overview'), charts=[
    ChartSpec(name='Events', chart_type='line_chart', queries=[Query(sql_query='SELECT 1')])])
  detailed = deepcopy(dashboard_data)
  attrs = detailed['attributes']
  assert isinstance(attrs, dict)
  attrs.update(charts=[{'id': 567, 'chart_type': 'line_chart', 'name': 'Events', 'x': 0, 'y': 0, 'w': 6, 'h': 4}],
    sections=[], has_overlaps=False)
  client, request = fake_client(
    response({'data': [], 'pagination': {}}), response({'data': dashboard_data}),
    response({'data': chart_data}), response({'data': detailed}),
    response({'data': [dashboard_data], 'pagination': {}}), response({'data': detailed}),
    response({'data': detailed}), response({'data': chart_data}), response({'data': detailed}))
  utest_val('1234', push_dashboard(client, definition).id)
  utest_val('1234', push_dashboard(client, definition).id)
  writes = [(c.args[0], c.args[1].removeprefix(api_url)) for c in request.call_args_list if c.args[0] != 'GET']
  utest_val([('POST', '/dashboards'), ('POST', '/dashboards/1234/charts'),
    ('PATCH', '/dashboards/1234'), ('PATCH', '/dashboards/1234/charts/567')], writes)


@utest_run
def unnamed_remote_chart_is_retained() -> None:
  definition = DashboardDefinition(dashboard=DashboardSpec(name='Overview'), charts=[
    ChartSpec(name='Events', chart_type='line_chart', queries=[Query(sql_query='SELECT 1')])])
  detailed = deepcopy(dashboard_data)
  attrs = detailed['attributes']
  assert isinstance(attrs, dict)
  attrs.update(charts=[{'id': 111, 'chart_type': 'line_chart', 'name': None, 'x': 0, 'y': 0, 'w': 6, 'h': 4},
    {'id': 222, 'chart_type': 'line_chart', 'name': ' ', 'x': 0, 'y': 4, 'w': 6, 'h': 4}], sections=[])
  client, request = fake_client(
    response({'data': [dashboard_data], 'pagination': {}}), response({'data': detailed}),
    response({'data': detailed}), response({'data': chart_data}), response({'data': detailed}))
  push_dashboard(client, definition)
  writes = [(c.args[0], c.args[1].removeprefix(api_url)) for c in request.call_args_list if c.args[0] != 'GET']
  utest_val([('PATCH', '/dashboards/1234'), ('POST', '/dashboards/1234/charts')], writes)
  duplicate = deepcopy(detailed)
  attrs = duplicate['attributes']
  assert isinstance(attrs, dict)
  attrs['charts'] = [{'id': i, 'chart_type': 'line_chart', 'name': 'Events', 'x': 0, 'y': 0, 'w': 6, 'h': 4} for i in (1, 2)]
  client, request = fake_client(response({'data': [dashboard_data], 'pagination': {}}), response({'data': duplicate}))
  utest_exc(ValueError, push_dashboard, client, definition)
  utest_val(2, request.call_count)


@utest_run
def ambiguous_names() -> None:
  definition = DashboardDefinition(dashboard=DashboardSpec(name='Overview'))
  client, request = fake_client(response({'data': [dashboard_data, dashboard_data], 'pagination': {}}))
  utest_exc(ValueError, push_dashboard, client, definition)
  utest_val(1, request.call_count)
  chart = ChartSpec(name='Same', chart_type='line_chart', queries=[])
  definition.charts = [chart, chart]
  client, request = fake_client()
  utest_exc(ValueError, push_dashboard, client, definition)
  utest_val(0, request.call_count)


@utest_run
def component_endpoints() -> None:
  section_data:JsonDict = {'id': '890', 'type': 'section', 'attributes': {
    'name': 'Logs', 'y': 0, 'collapsed': False, 'explanation': None}}
  client, request = fake_client(
    response({'data': [chart_data]}), response({'data': chart_data}), response({}, 204),
    response({'data': [section_data]}), response({'data': section_data}), response({'data': section_data}),
    response({'data': section_data}), response({}, 204))
  utest_val('567', client.list_charts('1234')[0].id)
  utest_val('567', client.get_chart('1234', '567').id)
  client.delete_chart('1234', '567')
  utest_val('890', client.list_sections('1234')[0].id)
  utest_val('890', client.get_section('1234', '890').id)
  client.create_section('1234', SectionSpec(name='Logs', y=0))
  utest_val({'name': 'Logs', 'y': 0, 'collapsed': False}, request.call_args.kwargs['json'])
  client.update_section('1234', '890', {'explanation': None})
  utest_val({'explanation': None}, request.call_args.kwargs['json'])
  client.delete_section('1234', '890')
  utest_val(('DELETE', api_url + '/dashboards/1234/sections/890'), request.call_args.args)


@utest_run
def resume_partial_push() -> None:
  definition = DashboardDefinition(dashboard=DashboardSpec(name='Overview'), charts=[
    ChartSpec(name='Events', chart_type='line_chart', queries=[Query(sql_query='SELECT 1')])])
  detailed = deepcopy(dashboard_data)
  attrs = detailed['attributes']
  assert isinstance(attrs, dict)
  attrs.update(charts=[], sections=[])
  client, request = fake_client(
    response({'data': [], 'pagination': {}}), response({'data': dashboard_data}), response({'errors': 'Retry later'}, 503),
    response({'data': [dashboard_data], 'pagination': {}}), response({'data': detailed}),
    response({'data': detailed}), response({'data': chart_data}), response({'data': detailed}))
  utest_exc(BetterStackError, push_dashboard, client, definition)
  push_dashboard(client, definition)
  utest_val(1, sum(c.args == ('POST', api_url + '/dashboards') for c in request.call_args_list))


@utest_run
def invalid_queries_fail_before_writes() -> None:
  chart = ChartSpec(name='Events', chart_type='line_chart', queries=[Query(query_type='query_builder')])
  definition = DashboardDefinition(dashboard=DashboardSpec(name='Overview'), charts=[chart])
  client, request = fake_client()
  utest_exc(ValueError, push_dashboard, client, definition)
  utest_val(0, request.call_count)
  utest_exc(ValueError, Query().as_json)


@utest_run
def source_pagination() -> None:
  source_data:JsonDict = {'id': '95', 'type': 'source', 'attributes': {
    'name': 'test1', 'platform': 'vector', 'table_name': 'test1', 'team_id': 1, 'team_name': 'My Team',
    'ingesting_paused': False, 'ingesting_host': 'example.betterstackdata.com', 'source_group_id': None,
    'token': 'fake-ingestion-secret', 'custom_bucket': {'secret_access_key': 'fake-bucket-secret'}}}
  other = deepcopy(source_data)
  attrs = other['attributes']
  assert isinstance(attrs, dict)
  attrs['team_name'] = 'Other team'
  client, request = fake_client(
    response({'data': [other], 'pagination': {'next': 'https://untrusted.example/page2'}}),
    response({'data': [source_data], 'pagination': {'next': None}}))
  sources = list(client.iter_sources())
  utest_val(['95'], [s.id for s in sources])
  utest_val('test1', sources[0].attributes.name)
  encoded = dumps(sources[0].as_json())
  assert 'fake-ingestion-secret' not in encoded and 'fake-bucket-secret' not in encoded
  assert 'fake-ingestion-secret' not in repr(sources[0])
  utest_val([1, 2], [c.kwargs['params']['page'] for c in request.call_args_list])
  for call in request.call_args_list:
    utest_val(('GET', api_url + '/sources'), call.args)
    utest_val(50, call.kwargs['params']['per_page'])
  utest_exc(ValueError, client.list_sources, per_page=51)
  utest_exc(ValueError, client.list_sources, page=0)
  client, request = fake_client(response({'data': [], 'pagination': {'next': None}}))
  utest_val([], list(client.iter_sources()))


@utest_run
def metric_pagination_and_writes() -> None:
  spec = MetricSpec(name='level', sql_expression="JSONExtract(raw, 'level', 'Nullable(String)')")
  data:JsonDict = {'id': 'g-123', 'type': 'metric', 'attributes': {**spec.as_json(), 'type': 'string_low_cardinality'}}
  client, request = fake_client(
    response({'data': [data], 'pagination': {'next': 'https://untrusted.example/page2'}}),
    response({'data': [], 'pagination': {}}), response({'data': data}), response({'data': data}))
  utest_val(['g-123'], [m.id for m in client.iter_metrics('95')])
  utest_val([1, 2], [c.kwargs['params']['page'] for c in request.call_args_list])
  for call in request.call_args_list: utest_val(('GET', api_url + '/sources/95/metrics'), call.args)
  client.create_metric('95', spec)
  utest_val({**spec.as_json(), 'team_name': 'My Team'}, request.call_args.kwargs['json'])
  client.update_metric('95', 'g-123', spec)
  utest_val(('PATCH', api_url + '/sources/95/metrics/g-123'), request.call_args.args)
  utest_val(spec.as_json(), request.call_args.kwargs['json'])
  utest_exc(ValueError, client.list_metrics, '95', page=0)
  utest_exc(ValueError, client.list_metrics, '95', per_page=51)


@utest_run
def metric_sync_resumes_and_skips_unchanged_rules() -> None:
  first = MetricSpec(name='level', sql_expression='new expression')
  second = MetricSpec(name='args.c', sql_expression='status expression')
  old:JsonDict = {'id': 'g-1', 'type': 'metric', 'attributes': {
    'name': 'level', 'sql_expression': 'old expression', 'aggregations': []}}
  updated:JsonDict = {'id': 'g-1', 'type': 'metric', 'attributes': first.as_json()}
  created:JsonDict = {'id': 'g-2', 'type': 'metric', 'attributes': second.as_json()}
  unrelated:JsonDict = {'id': 'm-3', 'type': 'metric', 'attributes': {
    'name': 'duration', 'sql_expression': 'duration expression', 'aggregations': ['avg']}}
  client, request = fake_client(
    response({'data': [old, unrelated], 'pagination': {}}), response({'data': updated}),
    response({'errors': 'Try later'}, 503),
    response({'data': [updated, unrelated], 'pagination': {}}), response({'data': created}),
    response({'data': [updated, created, unrelated], 'pagination': {}}))
  client.team_name = None
  utest_exc(BetterStackError, push_metrics, client, '95', [first, second])
  push_metrics(client, '95', [first, second])
  push_metrics(client, '95', [first, second])
  utest_val(['GET', 'PATCH', 'POST', 'GET', 'POST', 'GET'], [c.args[0] for c in request.call_args_list])


@utest_run
def metric_sync_rejects_ambiguity_and_wrong_team() -> None:
  spec = MetricSpec(name='level', sql_expression='expression')
  data:JsonDict = {'id': 'g-1', 'type': 'metric', 'attributes': spec.as_json()}
  client, request = fake_client(response({'data': [data, data], 'pagination': {}}))
  client.team_name = None
  utest_exc(ValueError, push_metrics, client, '95', [spec, spec])
  utest_val(0, request.call_count)
  utest_exc(ValueError, push_metrics, client, '95', [spec])
  utest_val(1, request.call_count)
  source:JsonDict = {'id': '95', 'type': 'source', 'attributes': {
    'name': 'test1', 'platform': 'vector', 'table_name': 'test1', 'team_id': 1, 'team_name': 'Other team',
    'ingesting_paused': False, 'ingesting_host': 'example.betterstackdata.com'}}
  client, request = fake_client(response({'data': source}))
  utest_exc(ValueError, push_metrics, client, '95', [spec])
  utest_val(1, request.call_count)
  utest_val(('GET', api_url + '/sources/95'), request.call_args.args)
