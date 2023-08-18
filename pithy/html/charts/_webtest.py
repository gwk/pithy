#!/usr/bin/env python3

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

  html.head.append(Css('''
  *, *::before, *::after { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0;
    padding: 0.5em;
    font-family: sans-serif;
  }
  '''))
  html.head.add_stylesheet('/static/pithy/charts.css')
  html.head.add_js(url='/static/pithy/charts.js')

  figure = chart_figure(
    title='CHART 1',
    y=LinearAxis(tick_step=10),
    series=[
      BarSeries(name='Series0', points=[(str(i), i) for i in range(51)]),
      #BarSeries(name='Series1', points=[('a', 4), ('b', 5), ('c', 6)]),
    ])

  html.body.append(figure)

  return HTMLResponse(content=html.render_str())
