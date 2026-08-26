# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.html.charts import BarSeries, chart_figure
from utest import utest, utest_val


series_a = BarSeries(name='a', points=[('x', 1)])
series_b = BarSeries(name='b', points=[('x', 2)])
chart_figure(series=[series_a, series_b])
utest_val((0, 2), (series_a.kind_idx, series_a.kind_count), desc='first bar series cluster position')
utest_val((1, 2), (series_b.kind_idx, series_b.kind_count), desc='second bar series cluster position')


def negative_bar_html() -> str:
  chart = chart_figure(series=[BarSeries(name='negative', points=[('x', -2), ('y', 2)])])
  return chart.render_str()


utest(True, lambda html: '--v-min:0.0000;--v-size:0.5000' in html, negative_bar_html())
utest(True, lambda html: '--v-min:0.5000;--v-size:0.5000' in html, negative_bar_html())


def integer_labels_html() -> str:
  'Integer x values must be treated as categories, not as a numerical axis.'
  chart = chart_figure(series=[BarSeries(name='years', points=[(2022, 4), (2023, 7), (2024, 5)])])
  return chart.render_str()


utest(True, lambda html: "class='chart categorical-numerical'" in html, integer_labels_html())
utest(True, lambda html: "--nx:3;" in html, integer_labels_html())
utest(True, lambda html: "<span class='label'>2022</span>" in html, integer_labels_html())
utest(True, lambda html: '--i:2;' in html, integer_labels_html()) # Bars are positioned by category index.
