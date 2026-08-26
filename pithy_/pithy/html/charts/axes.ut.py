# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.html.charts import BarSeries, LinearAxis
from utest import utest


def configured_constant_axis(value:float) -> LinearAxis:
  series = BarSeries(name='constant', points=[('a', value), ('b', value)])
  return LinearAxis().configure([series])


utest((1.5, 4.5), lambda axis: (axis.min, axis.max), configured_constant_axis(3))
utest((-1.0, 1.0), lambda axis: (axis.min, axis.max), configured_constant_axis(0))
utest((0.0, 1.0), lambda axis: (axis.min, axis.max), LinearAxis(show_origin=True).configure([]))
utest((-1.0, 1.0), lambda axis: (axis.min, axis.max), LinearAxis(show_origin=True, symmetric=True).configure([]))
