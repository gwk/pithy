# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.text_charts import chart_inline
from utest import utest


utest('', chart_inline, range(0))
utest('▒', chart_inline, range(1))
utest(' █', chart_inline, range(2))
utest(' ▄█', chart_inline, range(3))
utest(' ▁▂▃▄▅▆▇█', chart_inline, range(9))
