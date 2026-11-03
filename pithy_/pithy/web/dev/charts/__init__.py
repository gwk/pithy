# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
Demos of `pithy.html.charts`.

The index links to one page per chart kind.
Each kind has its own module, which renders its page through `chart_page` with figures grouped into sections by feature.
To add a kind, add its module, register its route in `dev.routes`, and list it in `chart_kinds`.
'''

from dataclasses import dataclass
from typing import Iterable, Sequence

from ....html import A, Code, Div, Figure, H1, H2, Li, Main, P, Section, Ul
from ...request import Request
from ...response import HtmlResponse
from ..pages import dev_page


_context_keywords_ = ['chart demo', 'data visualization', 'visual testing']


chart_kinds = (
  ('/charts/bars', 'Bar Charts', 'Vertical bars for categorical data: labels, values, clustered series and axis options.'),
)
'The chart kinds listed on the index, each as (path, label, description).'


def dev_charts_index(request:Request) -> HtmlResponse:
  'Index of chart demos.'
  return dev_page(title='Charts', breadcrumbs=[('/', 'Home'), ('/charts', 'Charts')],
    main=Main(H1('Charts'),
      P('Charts rendered as HTML and CSS by ', Code('pithy.html.charts'), '. Each page demonstrates one kind of chart.'),
      Ul(*(Li(A(href=path, _=label), ': ', desc) for path, label, desc in chart_kinds))))


def chart_page(*, path:str, title:str, intro:str, sections:Iterable[ChartSection]) -> HtmlResponse:
  'Render a page for one chart kind.'
  main = Main(H1(title), P(intro))
  for section in sections:
    main.append(Section(H2(section.heading), Div(cl=['chart-grid', 'wide' if section.wide else 'compact'], _=section.figures)))
  return dev_page(title=title, main=main, breadcrumbs=[('/', 'Home'), ('/charts', 'Charts'), (path, title)],
    css_paths=['/static/pithy/charts.css', '/static/dev/charts.css'])


@dataclass(frozen=True)
class ChartSection:
  '''
  A titled group of figures demonstrating one feature.

  Figures are laid out in a grid of small charts, unless `wide` gives each figure the full width.
  '''
  heading:str
  figures:Sequence[Figure]
  wide:bool = False
