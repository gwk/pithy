# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.stats import basic_stats, BasicStats
from utest import utest


utest(BasicStats(count=0, min=0, max=0, mean=0, median=0, variance=0, std_dev=0), basic_stats, [])


utest(BasicStats(count=1, min=0, max=0, mean=0.0, median=0, variance=0.0, std_dev=0.0), basic_stats, [0])
utest(BasicStats(count=1, min=1, max=1, mean=1.0, median=1, variance=0.0, std_dev=0.0), basic_stats, [1])
utest(BasicStats(count=2, min=0, max=1, mean=0.5, median=0.5, variance=0.5, std_dev=0.7071067811865476), basic_stats, [0, 1])
