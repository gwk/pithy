from pithy.string import fmt_rows
from utest import utest_seq


utest_seq([], fmt_rows, [])

utest_seq(['1    22  ', '333  4444'], fmt_rows, [(1, 22), (333, 4444)])
utest_seq(['  1    22', '333  4444'], fmt_rows, [(1, 22), (333, 4444)], rjust=True)
