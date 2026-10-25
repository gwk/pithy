# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Push a repository-owned saved query and its alert using a team-scoped Telemetry token.
Names identify managed resources. Unrelated resources are retained; duplicate names fail before writes.
Updates replace query and variable arrays. Run one writer at a time; pushes are not atomic.
'''

from collections.abc import Iterable

from pithy.json import JsonDict, req_json_dict

from .client import Client


_context_keywords_ = ['alerts', 'better stack', 'explorations', 'reconciliation', 'saved queries', 'telemetry']


def push_exploration_alert(client:Client, exploration:JsonDict, alert:JsonDict) -> tuple[JsonDict,JsonDict]:
  '''
  Create or update a named exploration and alert. New alerts start paused.
  Alert updates preserve notification routing and paused state unless explicitly supplied in `alert`.
  Use a team-scoped token to keep name matching within one team; global-token reconciliation is not supported.
  After a partial failure, rerun with the same names to resume.
  '''
  if client.team_name is not None: raise ValueError('Exploration reconciliation requires a team-scoped token.')
  for spec in (exploration, alert):
    if not isinstance(spec.get('name'), str) or not str(spec['name']).strip():
      raise ValueError('Exploration and alert names must not be empty.')
  existing = _named(client.iter_explorations(), str(exploration['name']))
  existing_alert = None
  if existing is not None:
    existing_alert = _named(client.iter_exploration_alerts(str(existing['id'])), str(alert['name']))
    saved = client.update_exploration(str(existing['id']), exploration)
  else:
    saved = client.create_exploration(exploration)
  exploration_id = str(saved['id'])
  if existing_alert is None:
    saved_alert = client.create_exploration_alert(exploration_id, {'paused': True, **alert})
  else:
    saved_alert = client.update_exploration_alert(exploration_id, str(existing_alert['id']), alert)
  return saved, saved_alert


def _named(resources:Iterable[JsonDict], name:str) -> JsonDict|None:
  matches = [r for r in resources if req_json_dict(r['attributes']).get('name') == name]
  if len(matches) > 1: raise ValueError(f'Ambiguous resource name: {name!r}.')
  return matches[0] if matches else None
