
from pithy.histogram import Histogram
from utest import utest_items


utest_items([(0, 2), (2, 2), (4, 2), (6, 2), (8, 2)],
  Histogram, range(10), bin_width=2)

utest_items([(0.0, 3), (2.5, 2), (5.0, 3), (7.5, 2)],
  Histogram, range(10), bin_width=2.5)
