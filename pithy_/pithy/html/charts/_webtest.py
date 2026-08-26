# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from ...html import Css, Html
from ...web.app import WebApp
from ...web.request import Request
from ...web.response import HtmlResponse
from ...web.static import pithy_web_static_dir_path
from ..charts import BarSeries, chart_figure, LinearAxis


class ChartTestApp(WebApp):

  def handle_request(self, request:Request) -> HtmlResponse:
    request.allow_methods('GET', 'HEAD')
    return home_page()


def home_page() -> HtmlResponse:
  html = Html.doc(title='Chart Test')

  with open(f'{pithy_web_static_dir_path()}/charts.css') as f:
    html.head.append(Css(f.read()))

  html.head.append(Css('''
  *, *::before, *::after { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    display: flex;
    flex-direction: column;
    gap: 2em;
    margin: 0;
    padding: 0.5em;
    font-family: monospace;
  }
  figure.chart {
    height: 24em;
  }
  '''))

  body = html.body

  body.append(chart_figure(
    dbg=True,
    title='Full Width - Short Labels',
    y=LinearAxis(show_origin=True),
    series=[
      BarSeries(name='Series0', points=[(f'{i}', i) for i in reversed(range(51))]),
    ]))

  body.append(chart_figure(
    dbg=True,
    title='Full Width - Long Labels',
    y=LinearAxis(show_origin=True),
    series=[
      BarSeries(name='Series0', points=[(f'{i:,}', i) for i in range(0, 50_001, 1000)]),
    ]))

  body.append(chart_figure(
    dbg=True,
    title='Limited Width - Short Labels',
    y=LinearAxis(show_origin=True),
    style='max-width:24em; max-height:24em;',

    series=[
      BarSeries(name='Series1', points=[('a', 4), ('b', 5), ('c', 6), ('d', 7)]),
    ]))

  body.append(chart_figure(
    title='Constant Zero Values',
    series=[
      BarSeries(name='Zero', points=[('a', 0), ('b', 0), ('c', 0), ('d', 0)]),
    ]))

  body.append(chart_figure(
    title='Clustered Series',
    series=[
      BarSeries(name='Series0', legend='First', points=[('a', 3), ('b', 5), ('c', 4), ('d', 7)]),
      BarSeries(name='Series1', legend='Second', points=[('a', 6), ('b', 4), ('c', 8), ('d', 5)]),
    ]))

  body.append(chart_figure(
    title='Positive and Negative Values',
    series=[
      BarSeries(name='Series0', points=[('a', -6), ('b', -3), ('c', 0), ('d', 4), ('e', 7)]),
    ]))

  body.append(chart_figure(
    title='Integer Category Labels',
    series=[
      BarSeries(name='Series0', points=[(2022, 4), (2023, 7), (2024, 5), (2025, 8)]),
    ]))

  body.append(chart_figure(
    title='No Y-Axis Ticks',
    y=LinearAxis(ticks_max=0),
    series=[
      BarSeries(name='Series0', points=[('a', 4), ('b', 7), ('c', 5), ('d', 8)]),
    ]))

  body.append(chart_figure(
    title='Independent Tick and Grid Spacing',
    y=LinearAxis(grid_step=1, tick_step=2),
    series=[
      BarSeries(name='Series0', points=[('a', 4), ('b', 7), ('c', 5), ('d', 8)]),
    ]))

  body.append(chart_figure(
    title='Grid Hidden',
    y=LinearAxis(show_grid=False),
    series=[
      BarSeries(name='Series0', points=[('a', 4), ('b', 7), ('c', 5), ('d', 8)]),
    ]))

  body.append(chart_figure(
    title='Automatic Fractional Ticks',
    y=LinearAxis(tick_fmt=lambda v: f'{v:.3f}'),
    series=[
      BarSeries(name='Series0', points=[('a', 0.01), ('b', 0.025), ('c', 0.04), ('d', 0.05)]),
    ]))

  return HtmlResponse(body=html)
