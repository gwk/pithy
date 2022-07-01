#!/usr/bin/env python3

from utest import utest
from pithy.text_charts import chart_inline

utest('', chart_inline, range(0))
utest('▒', chart_inline, range(1))
utest(' █', chart_inline, range(2))
utest(' ▄█', chart_inline, range(3))
utest(' ▁▂▃▄▅▆▇█', chart_inline, range(9))
