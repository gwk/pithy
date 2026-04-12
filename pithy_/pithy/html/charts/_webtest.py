# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route

from ...html import Css, Html
from ...web.starlette import mount_for_static_pithy
from ..charts import BarSeries, chart_figure, LinearAxis


def app() -> Starlette:

  routes = [
    mount_for_static_pithy(),
    Route('/', home_page),
  ]
  return Starlette(routes=routes, debug=True)


async def home_page(request:Request) -> HTMLResponse:
  html = Html.doc(title='Chart Test')

  html.head.add_stylesheet('/static/pithy/charts.css')

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

  return HTMLResponse(content=html.render_str())
