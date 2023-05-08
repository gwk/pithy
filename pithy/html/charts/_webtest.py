#!/usr/bin/env python3


from pithy.html import Div, Html, Style
from pithy.html.charts import BarSeries, chart_css, chart_figure, LinearAxis
from pithy.markup import EscapedStr
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route


def app() -> Starlette:

  routes = [
    Route('/', home_page),
  ]
  return Starlette(routes=routes, debug=True)


async def home_page(request:Request) -> HTMLResponse:
  html = Html.doc(title='TEST')

  html.head.append(Style(_=EscapedStr('*, *::before, *::after { box-sizing: border-box; }')))
  html.head.append(Style(_=EscapedStr(chart_css)))


  figure = chart_figure(title='CHART',
  y=LinearAxis(tick_step=10),
  series=[
    BarSeries(name='Series0', points=[(str(i), i) for i in range(101)]),
    #BarSeries(name='Series1', points=[('a', 4), ('b', 5), ('c', 6)]),
  ])

  html.body.append(figure)

  return HTMLResponse(content=html.render_str())
