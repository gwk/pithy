# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''Synchronous Better Stack Telemetry v2 API. Mutations are never retried automatically.'''

from collections.abc import Iterator
from itertools import count
from typing import Self
from urllib.parse import quote
from warnings import warn

from pithy.json import Json, JsonDict, req_json_dict, req_json_list
from pithy.secrets import SecretStr
from requests import Session

from .models import (Chart, ChartSpec, Dashboard, DashboardPage, DashboardSpec, Metric, MetricPage, MetricSpec, Section,
  SectionSpec, Source, SourcePage)


_context_keywords_ = ['api', 'betterstack', 'client', 'dashboard', 'http', 'labels', 'metrics', 'requests', 'rest', 'telemetry']

api_url = 'https://telemetry.betterstack.com/api/v2'


class BetterStackError(Exception):
  'An unsuccessful HTTP response; body preserves validation errors and rate-limit details.'

  def __init__(self, status:int, body:Json, retry_after:str|None=None):
    self.status = status
    self.body = body
    self.retry_after = retry_after
    super().__init__(f'Better Stack HTTP {status}: {body}')


class Client:

  def __init__(self, token:SecretStr, *, team_name:str|None=None, timeout:float=30, session:Session|None=None):
    if not token: raise ValueError('A Telemetry API token is required.')
    if timeout <= 0: raise ValueError('Timeout must be positive.')
    self.token = token
    self.team_name = team_name
    self.timeout = timeout
    self.session = session if session is not None else Session()
    self._owns_session = session is None


  def __enter__(self) -> Self: return self


  def __exit__(self, *args:object) -> None:
    if self._owns_session: self.session.close()


  def _request(self, method:str, path:str, *, body:JsonDict|None=None, params:dict[str,str|int]|None=None) -> JsonDict:
    with self.session.request(method, api_url + path, json=body, params=params, timeout=self.timeout,
      headers={'Authorization': f'Bearer {self.token.val}', 'Accept': 'application/json'}, allow_redirects=False) as response:
      if not 200 <= response.status_code < 300:
        try: error = response.json()
        except ValueError: error = response.text
        raise BetterStackError(response.status_code, error, response.headers.get('Retry-After'))
      if response.status_code == 204: return {}
      result = req_json_dict(response.json())
      if result.get('warnings'): warn(f'Better Stack: {result["warnings"]}', stacklevel=3) # Attribute to the caller.
      return result


  def list_sources(self, *, page:int=1, per_page:int=50) -> SourcePage:
    if page < 1 or not 1 <= per_page <= 50: raise ValueError('Require page >= 1 and 1 <= per_page <= 50.')
    return SourcePage.from_json(self._request('GET', '/sources', params=dict(page=page, per_page=per_page)))


  def iter_sources(self) -> Iterator[Source]:
    'Iterate all source pages, filtering by client team when one is specified.'
    page = 1
    while True:
      result = self.list_sources(page=page)
      for source in result.data:
        if self.team_name is None or source.attributes.team_name == self.team_name: yield source
      if result.pagination.next is None: return
      if not result.data: raise ValueError('Empty source page has a next page.')
      page += 1 # Never send the token to a URL supplied in the response.


  def get_source(self, source_id:str) -> Source:
    return Source.from_json(req_json_dict(self._request('GET', _source_path(source_id))['data']))


  def list_metrics(self, source_id:str, *, page:int=1, per_page:int=50) -> MetricPage:
    if page < 1 or not 1 <= per_page <= 50: raise ValueError('Require page >= 1 and 1 <= per_page <= 50.')
    return MetricPage.from_json(self._request('GET', _source_path(source_id) + '/metrics',
      params=dict(page=page, per_page=per_page)))


  def iter_metrics(self, source_id:str) -> Iterator[Metric]:
    for page in count(1):
      result = self.list_metrics(source_id, page=page)
      yield from result.data
      if result.pagination.next is None: return
      if not result.data: raise ValueError('Empty metric page has a next page.')


  def create_metric(self, source_id:str, spec:MetricSpec) -> Metric:
    body = spec.as_json()
    if self.team_name is not None: body['team_name'] = self.team_name
    return Metric.from_json(req_json_dict(self._request('POST', _source_path(source_id) + '/metrics', body=body)['data']))


  def update_metric(self, source_id:str, metric_id:str, spec:MetricSpec) -> Metric:
    if not metric_id: raise ValueError('Metric ID must not be empty.')
    path = _source_path(source_id) + '/metrics/' + quote(metric_id, safe='')
    return Metric.from_json(req_json_dict(self._request('PATCH', path, body=spec.as_json())['data']))


  def list_dashboards(self, *, page:int=1, per_page:int=50, query:str|None=None,
   dashboard_group_id:int|None=None) -> DashboardPage:
    if page < 1 or not 1 <= per_page <= 250: raise ValueError('Require page >= 1 and 1 <= per_page <= 250.')
    params:dict[str,str|int] = dict(page=page, per_page=per_page)
    if query is not None: params['query'] = query
    if dashboard_group_id is not None: params['dashboard_group_id'] = dashboard_group_id
    return DashboardPage.from_json(self._request('GET', '/dashboards', params=params))


  def iter_dashboards(self, *, query:str|None=None, dashboard_group_id:int|None=None) -> Iterator[Dashboard]:
    page = 1
    while True:
      result = self.list_dashboards(page=page, per_page=250, query=query, dashboard_group_id=dashboard_group_id)
      yield from result.data
      if result.pagination.next is None: return
      if not result.data: raise ValueError('Empty dashboard page has a next page.')
      page += 1 # Never send the token to a URL supplied in the response.


  def get_dashboard(self, dashboard_id:str) -> Dashboard:
    return Dashboard.from_json(req_json_dict(self._request('GET', _path(dashboard_id))['data']))


  def create_dashboard(self, spec:DashboardSpec) -> Dashboard:
    body = spec.as_json()
    if self.team_name is not None: body['team_name'] = self.team_name
    return Dashboard.from_json(req_json_dict(self._request('POST', '/dashboards', body=body)['data']))


  def update_dashboard(self, dashboard_id:str, spec:DashboardSpec|JsonDict) -> Dashboard:
    body = spec.as_json() if isinstance(spec, DashboardSpec) else spec
    return Dashboard.from_json(req_json_dict(self._request('PATCH', _path(dashboard_id), body=body)['data']))


  def delete_dashboard(self, dashboard_id:str) -> None:
    self._request('DELETE', _path(dashboard_id))


  def export_dashboard(self, dashboard_id:str) -> JsonDict:
    'Return the export data suitable for import_dashboard, preserving the vendor-defined format.'
    return req_json_dict(self._request('GET', _path(dashboard_id) + '/export')['data'])


  def import_dashboard(self, data:JsonDict, *, name:str|None=None) -> Dashboard:
    'Create a new dashboard asynchronously; this cannot update an existing dashboard.'
    body:JsonDict = {'data': data}
    if name is not None: body['name'] = name
    if self.team_name is not None: body['team_name'] = self.team_name
    return Dashboard.from_json(req_json_dict(self._request('POST', '/dashboards/import', body=body)['data']))


  def list_charts(self, dashboard_id:str) -> list[Chart]:
    data = self._request('GET', _path(dashboard_id) + '/charts')['data']
    return [Chart.from_json(req_json_dict(v)) for v in req_json_list(data)]


  def get_chart(self, dashboard_id:str, chart_id:str) -> Chart:
    return Chart.from_json(req_json_dict(self._request('GET', _path(dashboard_id, 'charts', chart_id))['data']))


  def create_chart(self, dashboard_id:str, spec:ChartSpec) -> Chart:
    data = self._request('POST', _path(dashboard_id) + '/charts', body=spec.as_json())['data']
    return Chart.from_json(req_json_dict(data))


  def update_chart(self, dashboard_id:str, chart_id:str, spec:ChartSpec|JsonDict) -> Chart:
    body = spec.as_json() if isinstance(spec, ChartSpec) else spec
    data = self._request('PATCH', _path(dashboard_id, 'charts', chart_id), body=body)['data']
    return Chart.from_json(req_json_dict(data))


  def delete_chart(self, dashboard_id:str, chart_id:str) -> None:
    self._request('DELETE', _path(dashboard_id, 'charts', chart_id))


  def list_sections(self, dashboard_id:str) -> list[Section]:
    data = self._request('GET', _path(dashboard_id) + '/sections')['data']
    return [Section.from_json(req_json_dict(v)) for v in req_json_list(data)]


  def get_section(self, dashboard_id:str, section_id:str) -> Section:
    return Section.from_json(req_json_dict(self._request('GET', _path(dashboard_id, 'sections', section_id))['data']))


  def create_section(self, dashboard_id:str, spec:SectionSpec) -> Section:
    data = self._request('POST', _path(dashboard_id) + '/sections', body=spec.as_json())['data']
    return Section.from_json(req_json_dict(data))


  def update_section(self, dashboard_id:str, section_id:str, spec:SectionSpec|JsonDict) -> Section:
    body = spec.as_json() if isinstance(spec, SectionSpec) else spec
    data = self._request('PATCH', _path(dashboard_id, 'sections', section_id), body=body)['data']
    return Section.from_json(req_json_dict(data))


  def delete_section(self, dashboard_id:str, section_id:str) -> None:
    self._request('DELETE', _path(dashboard_id, 'sections', section_id))


def _path(dashboard_id:str, collection:str='', child_id:str='') -> str:
  if not dashboard_id: raise ValueError('Dashboard ID must not be empty.')
  path = '/dashboards/' + quote(dashboard_id, safe='')
  if collection:
    if not child_id: raise ValueError('Child ID must not be empty.')
    path += '/' + collection + '/' + quote(child_id, safe='')
  return path


def _source_path(source_id:str) -> str:
  if not source_id: raise ValueError('Source ID must not be empty.')
  return '/sources/' + quote(source_id, safe='')
