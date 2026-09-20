# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''Telemetry v2 dashboard models. Unknown response fields are ignored; chart settings remain open JSON objects.'''

from dataclasses import dataclass, field, fields
from typing import Any, Self

from pithy.json import Json, JsonDict
from pithy.transtruct import Transtructor


_context_keywords_ = ['api', 'betterstack', 'dashboard', 'dataclass', 'labels', 'metrics', 'telemetry']
_transtructor = Transtructor(strict=False)
_response = {'response': True} # Field metadata marking response-only fields that as_json omits.


@dataclass(kw_only=True)
class Model:

  @classmethod
  def from_json(cls, value:JsonDict) -> Self:
    return _transtructor.transtruct(cls, value)


  def as_json(self) -> JsonDict:
    'Encode request fields, omitting None and response-only fields. Raw JSON dictionaries preserve null values.'
    return {f.name: _encode(v) for f in fields(self)
      if not f.metadata.get('response') and (v := getattr(self, f.name)) is not None}


def _encode(value:Any) -> Json:
  if isinstance(value, Model): return value.as_json()
  if isinstance(value, (list, tuple)): return [_encode(v) for v in value]
  if isinstance(value, dict): return {k: _encode(v) for k, v in value.items()}
  if value is None or isinstance(value, (str, int, float, bool)): return value
  raise TypeError(f'Not a JSON value: {type(value).__name__}.')


@dataclass(kw_only=True)
class Variable(Model):
  name:str
  variable_type:str
  values:list[str] = field(default_factory=list)
  default_values:list[str] = field(default_factory=list)
  sql_definition:str|None = None
  allow_multiple_values:bool|None = None


@dataclass(kw_only=True)
class Query(Model):
  query_type:str = 'sql_expression'
  source_variable:str = 'source'
  sql_query:str|None = None
  where_condition:str|None = None
  static_text:str|None = None
  id:int|None = field(default=None, metadata=_response)
  name:str|None = field(default=None, metadata=_response)


  def as_json(self) -> JsonDict:
    required = {'sql_expression': self.sql_query, 'tail_query': self.where_condition, 'static_text': self.static_text}
    if self.query_type not in required: raise ValueError(f'Query type is not writable: {self.query_type!r}.')
    if required[self.query_type] is None: raise ValueError(f'Missing content for {self.query_type!r} query.')
    return super().as_json()


@dataclass(kw_only=True)
class ChartSpec(Model):
  chart_type:str
  name:str|None
  queries:list[Query]
  x:int|None = None
  y:int|None = None
  w:int = 6
  h:int = 4
  description:str|None = None
  settings:dict[str,Any] = field(default_factory=dict)


  def as_json(self) -> JsonDict:
    if not self.queries: raise ValueError('A chart requires at least one query.')
    if len(self.queries) > 1 and self.chart_type != 'line_chart':
      raise ValueError('Only line_chart supports multiple queries.')
    if self.w < 1 or self.h < 1: raise ValueError('Chart dimensions must be positive.')
    if (self.x is not None and self.x < 0) or (self.y is not None and self.y < 0):
      raise ValueError('Chart coordinates must be nonnegative.')
    return super().as_json()


@dataclass(kw_only=True)
class SectionSpec(Model):
  name:str
  y:int|None = None
  collapsed:bool = False
  explanation:str|None = None


@dataclass(kw_only=True)
class DashboardSpec(Model):
  'Dashboard request attributes. None means omitted; use raw PATCH JSON to explicitly send null.'
  name:str
  dashboard_group_id:int|None = None
  refresh_interval:int = 0
  date_range_from:str = 'now-3h'
  date_range_to:str = 'now'
  source_eligibility_sql:str|None = None
  variables:list[Variable]|None = None


@dataclass(kw_only=True)
class ChartSummary(Model):
  'The embedded chart in a dashboard response does not include queries or settings.'
  id:int
  chart_type:str
  name:str|None
  x:int
  y:int
  w:int
  h:int


@dataclass(kw_only=True)
class SectionSummary(SectionSpec):
  id:int = field(metadata=_response)


@dataclass(kw_only=True)
class DashboardAttributes(DashboardSpec):
  'Response attributes extend the request spec, so a fetched dashboard can be edited and passed to update_dashboard.'
  team_id:int = field(metadata=_response)
  team_name:str = field(metadata=_response)
  created_at:str = field(metadata=_response)
  updated_at:str = field(metadata=_response)
  charts:list[ChartSummary]|None = field(default=None, metadata=_response)
  sections:list[SectionSummary]|None = field(default=None, metadata=_response)
  has_overlaps:bool|None = field(default=None, metadata=_response)


@dataclass(kw_only=True)
class Dashboard(Model):
  id:str
  type:str
  attributes:DashboardAttributes


@dataclass(kw_only=True)
class Chart(Model):
  id:str
  type:str
  attributes:ChartSpec


@dataclass(kw_only=True)
class Section(Model):
  id:str
  type:str
  attributes:SectionSpec


@dataclass(kw_only=True)
class Pagination(Model):
  first:str|None = None
  last:str|None = None
  prev:str|None = None
  next:str|None = None


@dataclass(kw_only=True)
class DashboardPage(Model):
  data:list[Dashboard]
  pagination:Pagination


@dataclass(kw_only=True)
class SourceAttributes(Model):
  'Source metadata for discovery. Ingestion tokens and other credential fields are deliberately not retained.'
  name:str
  platform:str
  table_name:str
  team_id:int
  team_name:str
  ingesting_paused:bool
  ingesting_host:str
  source_group_id:int|None = None
  data_region:str|None = None


@dataclass(kw_only=True)
class Source(Model):
  id:str
  type:str
  attributes:SourceAttributes


@dataclass(kw_only=True)
class SourcePage(Model):
  data:list[Source]
  pagination:Pagination


@dataclass(kw_only=True)
class DashboardDefinition(Model):
  'A repository-owned composition, not a single API request or an import/export payload.'
  dashboard:DashboardSpec
  charts:list[ChartSpec] = field(default_factory=list)
  sections:list[SectionSpec] = field(default_factory=list)


@dataclass(kw_only=True)
class MetricSpec(Model):
  'A log extraction expression; an empty aggregations list defines a label.'
  name:str
  sql_expression:str
  aggregations:list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class Metric(Model):
  id:str
  type:str
  attributes:MetricSpec


@dataclass(kw_only=True)
class MetricPage(Model):
  data:list[Metric]
  pagination:Pagination
