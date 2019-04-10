#!/usr/bin/env python3

from utest import *
from pithy.text_charts import *

utest('', chart_seq_inline, range(0))
utest('▒', chart_seq_inline, range(1))
utest(' █', chart_seq_inline, range(2))
utest(' ▄█', chart_seq_inline, range(3))
utest(' ▁▂▃▄▅▆▇█', chart_seq_inline, range(9))
