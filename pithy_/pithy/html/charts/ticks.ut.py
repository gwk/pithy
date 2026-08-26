# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from typing import Any

from pithy.html.charts import calc_frac_len, LinearAxis
from utest import utest


utest(1, LinearAxis(min=0, max=10, ticks_max=11).configure([]).choose_ticks_step)
utest(2, LinearAxis(min=0, max=10, ticks_max=10).configure([]).choose_ticks_step)
utest(0.005, LinearAxis(min=0, max=0.05, ticks_max=11).configure([]).choose_ticks_step)

utest(0, calc_frac_len, [0, 5, 10])
utest(1, calc_frac_len, [0.1])
utest(2, calc_frac_len, [0, 0.25, 0.5])
utest(3, calc_frac_len, [0.005])
utest(1, calc_frac_len, [i/10 for i in range(11)]) # Float representation error must not demand excess digits.
utest(4, calc_frac_len, [1/3], 4) # A value that never matches is truncated to `max_frac_len`.


def tick_labels(axis:LinearAxis) -> list[str]:
  tick_fmt = axis.calc_tick_fmt()
  return [str(tick_fmt(v)) for v in axis.ticks]


def configured_axis(**kw:Any) -> LinearAxis:
  axis = LinearAxis(**kw).configure([])
  axis.tick_divs() # Fill in the ticks.
  return axis


# Fractional ticks must not be formatted as integers, which would render as duplicate labels.
utest(['0.0', '0.5', '1.0'], tick_labels, configured_axis(min=0, max=1, ticks_max=3))
utest(['0.00', '0.02', '0.04'], tick_labels, configured_axis(min=0, max=0.05, ticks_max=3))
utest(['0.000', '0.005', '0.010', '0.015', '0.020', '0.025', '0.030', '0.035', '0.040', '0.045', '0.050'],
  tick_labels, configured_axis(min=0, max=0.05, ticks_max=11))
utest(['0', '5', '10'], tick_labels, configured_axis(min=0, max=10, ticks_max=3))
utest(['0', '5,000', '10,000'], tick_labels, configured_axis(min=0, max=10_000, ticks_max=3))

# An explicitly specified step or tick set determines the precision.
utest(['0.00', '0.25', '0.50', '0.75', '1.00'], tick_labels, configured_axis(min=0, max=1, tick_step=0.25))
utest(['0.00', '0.25', '1.00'], tick_labels, configured_axis(min=0, max=1, ticks=[0, 0.25, 1]))

# An explicit tick_fmt is always honored.
utest(['0.00x', '1.00x'], tick_labels, configured_axis(min=0, max=1, ticks_max=2, tick_fmt=lambda v: f'{v:.2f}x'))
