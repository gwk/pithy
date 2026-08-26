# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.html.charts import BarSeries, chart_figure, LinearAxis
from utest import utest, utest_val


def configured_constant_axis(value:float) -> LinearAxis:
  series = BarSeries(name='constant', points=[('a', value), ('b', value)])
  return LinearAxis().configure([series])


utest((1.5, 4.5), lambda axis: (axis.min, axis.max), configured_constant_axis(3))
utest((-1.0, 1.0), lambda axis: (axis.min, axis.max), configured_constant_axis(0))
utest((0.0, 1.0), lambda axis: (axis.min, axis.max), LinearAxis(show_origin=True).configure([]))
utest((-1.0, 1.0), lambda axis: (axis.min, axis.max), LinearAxis(show_origin=True, symmetric=True).configure([]))

x = LinearAxis(min=0, max=10)
y = LinearAxis(min=0, max=20)
chart_figure(x=x, y=y, symmetric_xy=True)
utest_val((0.5, 1.0), (x.transform(10), x.transform(20)), desc='symmetric x transform')
utest_val((0.5, 1.0), (y.transform(10), y.transform(20)), desc='symmetric y transform')
