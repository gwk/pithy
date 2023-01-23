# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.


from pithy.markup import EscapedStr
from pithy.html import Html, Style, Div
from pithy.html.charts import BarSeries, chart_css, chart_figure, LinearAxis

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import HTMLResponse

def app() -> Starlette:

  routes = [
    Route('/', home_page),
  ]
  return Starlette(routes=routes, debug=True)


async def home_page(request:Request) -> HTMLResponse:
  html = Html.doc(title='TEST')

  html.head.append(Style(ch=EscapedStr('*, *::before, *::after { box-sizing: border-box; }')))
  html.head.append(Style(ch=EscapedStr(chart_css)))


  figure = chart_figure(title='CHART',
  y=LinearAxis(tick_step=10),
  series=[
    BarSeries(name='Series0', points=[(str(i), i) for i in range(101)]),
    #BarSeries(name='Series1', points=[('a', 4), ('b', 5), ('c', 6)]),
  ])

  html.body.append(figure)

  return HTMLResponse(content=html.render_str())
