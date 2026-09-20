# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''Push repository-owned dashboard definitions while preserving remote dashboard and component IDs.'''

from collections.abc import Iterable

from pithy.json import render_json

from .client import Client
from .models import Dashboard, DashboardDefinition


_context_keywords_ = ['betterstack', 'dashboard', 'push', 'sync', 'upsert']


def push_dashboard(client:Client, definition:DashboardDefinition, *, dashboard_id:str|None=None) -> Dashboard:
  '''
  Create or update by exact dashboard name and client team; an explicit ID also allows renaming the dashboard.
  Charts and sections match by unique, nonempty names. Unmatched and unnamed remote components are retained.
  Calls are sequential, not transactional. On partial failure, rerun with the same names to resume.
  Run only one writer at a time; the API has no unique-name or atomic upsert guarantee.
  '''
  spec = definition.dashboard
  if not spec.name.strip(): raise ValueError('Dashboard name must not be empty.')
  _unique_names(c.name for c in definition.charts)
  _unique_names(s.name for s in definition.sections)
  # Serialize the whole definition before any writes so invalid JSON values fail locally.
  render_json(definition.as_json(), allow_nan=False)

  if dashboard_id is None:
    matches = [d for d in client.iter_dashboards(query=spec.name) if d.attributes.name == spec.name
      and (client.team_name is None or d.attributes.team_name == client.team_name)]
    if len(matches) > 1: raise ValueError(f'Ambiguous dashboard name: {spec.name!r}; specify an ID.')
    if matches: dashboard_id = matches[0].id

  if dashboard_id is None:
    current = client.create_dashboard(spec)
    dashboard_id = current.id
    chart_ids:dict[str,str] = {}
    section_ids:dict[str,str] = {}
  else:
    current = client.get_dashboard(dashboard_id)
    if client.team_name is not None and current.attributes.team_name != client.team_name:
      raise ValueError('Dashboard belongs to a different team.')
    charts = current.attributes.charts
    sections = current.attributes.sections
    if charts is None or sections is None: raise ValueError('Expected a detailed dashboard response.')
    chart_ids = _remote_ids((c.name, c.id) for c in charts)
    section_ids = _remote_ids((s.name, s.id) for s in sections)
    client.update_dashboard(dashboard_id, spec)

  for section in definition.sections:
    if section.name in section_ids: client.update_section(dashboard_id, section_ids[section.name], section)
    else: client.create_section(dashboard_id, section)
  for chart in definition.charts:
    assert chart.name is not None
    if chart.name in chart_ids: client.update_chart(dashboard_id, chart_ids[chart.name], chart)
    else: client.create_chart(dashboard_id, chart)
  return client.get_dashboard(dashboard_id)


def _unique_names(names:Iterable[str|None]) -> None:
  seen:set[str] = set()
  for name in names:
    if name is None or not name.strip(): raise ValueError('Managed components require nonempty names.')
    if name in seen: raise ValueError(f'Ambiguous component name: {name!r}.')
    seen.add(name)


def _remote_ids(components:Iterable[tuple[str|None,int]]) -> dict[str,str]:
  'Map nonempty remote component names to IDs. Unnamed remote components are never matched, so they are retained untouched.'
  ids:dict[str,str] = {}
  for name, id in components:
    if name is None or not name.strip(): continue
    if name in ids: raise ValueError(f'Ambiguous remote component name: {name!r}.')
    ids[name] = str(id)
  return ids
