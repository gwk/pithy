# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from collections.abc import Sequence

from .client import Client
from .models import Metric, MetricSpec


_context_keywords_ = ['betterstack', 'labels', 'metrics', 'sync', 'upsert']


def push_metrics(client:Client, source_id:str, specs:Sequence[MetricSpec]) -> None:
  'Upsert named extraction rules, retaining unrelated rules and skipping unchanged definitions.'
  names = [spec.name for spec in specs]
  if any(not name.strip() for name in names) or len(set(names)) != len(names):
    raise ValueError('Metrics require unique, nonempty names.')
  if any(not spec.sql_expression.strip() for spec in specs): raise ValueError('Metric expressions must not be empty.')
  if client.team_name is not None and client.get_source(source_id).attributes.team_name != client.team_name:
    raise ValueError('Source belongs to a different team.')
  current:dict[str,Metric] = {}
  for metric in client.iter_metrics(source_id):
    name = metric.attributes.name
    if name not in names: continue
    if name in current: raise ValueError(f'Ambiguous metric name: {name!r}.')
    current[name] = metric
  for spec in specs:
    if (existing := current.get(spec.name)) is None:
      client.create_metric(source_id, spec)
    elif existing.attributes != spec:
      client.update_metric(source_id, existing.id, spec)
