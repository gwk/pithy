# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'Bar chart demos.'

from ....html.charts import BarSeries, chart_figure, LinearAxis
from ...request import Request
from ...response import HtmlResponse
from . import chart_page, ChartSection


def dev_charts_bars(request:Request) -> HtmlResponse:
  'Bar charts, grouped by feature.'
  return chart_page(path='/charts/bars', title='Bar Charts',
    intro='BarSeries renders categorical data as vertical bars. Several series form a cluster of bars per category.',
    sections=[

    ChartSection('Category Labels', wide=True, figures=[
      chart_figure(title='Many Short Labels', y=LinearAxis(show_origin=True),
        series=[BarSeries(name='Series0', points=[(f'{i}', i) for i in reversed(range(51))])]),
      chart_figure(title='Many Long Labels', y=LinearAxis(show_origin=True),
        series=[BarSeries(name='Series0', points=[(f'{i:,}', i) for i in range(0, 50_001, 1000)])]),
    ]),

    ChartSection('Values', figures=[
      chart_figure(title='Few Short Labels', y=LinearAxis(show_origin=True),
        series=[BarSeries(name='Series1', points=[('a', 4), ('b', 5), ('c', 6), ('d', 7)])]),
      chart_figure(title='Constant Zero Values',
        series=[BarSeries(name='Zero', points=[('a', 0), ('b', 0), ('c', 0), ('d', 0)])]),
      chart_figure(title='Positive and Negative Values',
        series=[BarSeries(name='Series0', points=[('a', -6), ('b', -3), ('c', 0), ('d', 4), ('e', 7)])]),
      chart_figure(title='Automatic Fractional Ticks',
        series=[BarSeries(name='Series0', points=[('a', 0.01), ('b', 0.025), ('c', 0.04), ('d', 0.05)])]),
      chart_figure(title='Integer Category Labels',
        series=[BarSeries(name='Series0', points=[(2022, 4), (2023, 7), (2024, 5), (2025, 8)])]),
    ]),

    ChartSection('Series', figures=[
      chart_figure(title='Clustered Series', series=[
        BarSeries(name='Series0', legend='First', points=[('a', 3), ('b', 5), ('c', 4), ('d', 7)]),
        BarSeries(name='Series1', legend='Second', points=[('a', 6), ('b', 4), ('c', 8), ('d', 5)]),
      ]),
    ]),

    ChartSection('Value Axis', figures=[
      chart_figure(title='No Y-Axis Ticks', y=LinearAxis(ticks_max=0),
        series=[BarSeries(name='Series0', points=[('a', 4), ('b', 7), ('c', 5), ('d', 8)])]),
      chart_figure(title='Independent Tick and Grid Spacing', y=LinearAxis(grid_step=1, tick_step=2),
        series=[BarSeries(name='Series0', points=[('a', 4), ('b', 7), ('c', 5), ('d', 8)])]),
      chart_figure(title='Grid Hidden', y=LinearAxis(show_grid=False),
        series=[BarSeries(name='Series0', points=[('a', 4), ('b', 7), ('c', 5), ('d', 8)])]),
    ]),
  ])
