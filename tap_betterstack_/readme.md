# tap_betterstack

Better Stack Telemetry v2 API and composable Python dashboard definitions.
Uses Pithy's dataclass conversion and JSON types, and the existing `requests` dependency.

## Definitions

```python
from pithy.secrets import SecretStr
from tap_betterstack.client import Client
from tap_betterstack.dashboards import push_dashboard
from tap_betterstack.models import ChartSpec, DashboardDefinition, DashboardSpec, Query, Variable

def overview(stage:str, source_id:str) -> DashboardDefinition:
  return DashboardDefinition(
    dashboard=DashboardSpec(name=f'My app / {stage}', variables=[
      Variable(name='source', variable_type='source', values=[source_id], default_values=[source_id])]),
    charts=[ChartSpec(name='Events', chart_type='line_chart', x=0, y=0, queries=[Query(sql_query='''
SELECT {{time}} AS time, sum(logs_count) AS value
FROM {{source}}
WHERE dt BETWEEN {{start_time}} AND {{end_time}}
GROUP BY time
ORDER BY time
''')])])

# Render overview(...).as_json() for offline review. To push:
# with Client(SecretStr(token), team_name='My Team') as client:
#   dashboard = push_dashboard(client, overview('test1', source_id))
#   print(dashboard.id)
```

`{{source}}` is the aggregated metrics table, so `count(*)` does not count events, even though some vendor API examples use it.
Count logs with `sum(logs_count)`, or all event types with `countMerge(events_count)`; see [Writing SQL queries](https://betterstack.com/docs/logs/dashboards/sql-queries/).

Repository functions can share chart constructors, vary source IDs, or add components conditionally for production.
`DashboardDefinition` is a local composition of separate dashboard, chart, and section requests, not the API import format.
Source IDs are account-specific; ingestion tokens and source display names are not source IDs.
Use a Telemetry management API token, not a Vector ingestion token. Global tokens also require `team_name` for creation.

## Source metrics and labels

`MetricSpec(name=..., sql_expression=..., aggregations=[])` defines a label extracted from raw log JSON.
Use a nonempty aggregations list for a numeric metric.
`Client` provides `list_metrics`, `iter_metrics`, `create_metric`, and `update_metric` for a source ID.
`tap_betterstack.metrics.push_metrics(client, source_id, specs)` matches rules by name, creates missing rules, updates changed rules, and skips identical definitions.
It validates source team ownership when a team name is supplied and retains unrelated rules.
Apply extraction rules before dashboards that query their labels.
Updates use the API's default `new_data` behavior; this helper does not request historical reprocessing.
Calls are sequential and non-atomic; rerun after a partial failure with the same names.

See the [Metrics API](https://betterstack.com/docs/logs/api/list-all-existing-metrics/) for details.

## Iteration

`push_dashboard` finds an exact dashboard name within the client's team, or accepts an explicit `dashboard_id`.
Charts and sections match by unique nonempty names; matching objects retain their IDs.
Duplicate names fail before writes. Keep component names stable; use the individual update methods with IDs to rename them.
Objects removed from the definition remain remotely, as do unnamed remote charts. Remove them explicitly with the delete methods after reviewing their IDs.
Fields left as `None` are omitted from requests and left alone remotely; this is an update workflow, not exact reconciliation of all remote state.
Fields with concrete defaults, such as `refresh_interval`, `date_range_from`, `date_range_to`, `collapsed`, `w` and `h`, are always sent and overwrite remote values on every push.
Only use it on dashboards owned by these definitions: matching names designate managed components.

Pushes use multiple requests and are not atomic. A failure can leave partial progress; rerun with the same names to resume.
There is no automatic retry for writes, nor a server-side unique-name guarantee. Serialize writers.
After an uncertain timeout on creation, inspect the dashboard list before retrying.
Better Stack may adjust overlapping layouts asynchronously, so choose nonoverlapping grid coordinates.

## API and models

`Client` provides list/get/create/update/delete methods for dashboards, charts, and sections, plus dashboard export/import.
`list_dashboards` returns a `DashboardPage`; `iter_dashboards` traverses all pages.
`list_sources` returns a `SourcePage`; `iter_sources` traverses all pages and filters by the client's optional team name.
Source models retain discovery metadata and omit ingestion tokens and other credential fields from the [Sources API response](https://betterstack.com/docs/logs/api/list-all-existing-sources/).
Resources preserve the API's `id`, `type`, and `attributes` structure. IDs in resource envelopes are strings; embedded IDs are integers.
Dashboard lists omit charts and sections (`None`); detail responses contain lists (possibly empty).
Chart summaries embedded in dashboards omit queries and settings; use `get_chart` for those.
Read-only query IDs and names are omitted from request serialization. Unknown response fields are ignored.
Chart-specific settings remain dictionaries rather than an incomplete catalog of vendor options.

Request dataclasses omit `None`, but preserve empty arrays, false, zero, and null values within settings.
Update methods also accept raw JSON dictionaries for partial patches and explicit null values, e.g. `{'dashboard_group_id': None}`.
Supplying `queries` replaces the entire query array; supplying `settings` replaces the entire settings object.
The API supports writing SQL, tail, and static-text queries. Query-builder, PQL, and funnel queries can be read but not written.

Export/import uses a different schema, including `preset` and `chart_queries`.
`export_dashboard` returns the response's inner `data` object, ready for `import_dashboard`.
Import always creates a new dashboard and queues asynchronous processing; it is not an update mechanism.

The client uses a timeout, rejects redirects, and raises `BetterStackError` with status, error body, and `Retry-After`.
Network errors propagate from requests. Run synchronous calls in a worker thread when using asyncio.

## References

* [Dashboard API](https://betterstack.com/docs/logs/api/dashboards/list/)
* [Dashboard creation and variables](https://betterstack.com/docs/logs/api/dashboards/create/)
* [Chart creation and supported query types](https://betterstack.com/docs/logs/api/charts/create/)
* [Chart updates](https://betterstack.com/docs/logs/api/charts/update/)
* [Sections](https://betterstack.com/docs/logs/api/dashboard-sections/create/)
* [Export](https://betterstack.com/docs/logs/api/dashboards/export/) and [import](https://betterstack.com/docs/logs/api/dashboards/import/)
