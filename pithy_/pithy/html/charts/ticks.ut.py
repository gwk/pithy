# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.html.charts import LinearAxis
from utest import utest


utest(1, LinearAxis(min=0, max=10, ticks_max=11).configure([]).choose_ticks_step)
utest(2, LinearAxis(min=0, max=10, ticks_max=10).configure([]).choose_ticks_step)
