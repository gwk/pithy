# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from operator import add

from pithy.date import Date, DateDelta, is_leap_year
from utest import utest, utest_val


j1 = Date(2000, 1, 1)
utest_val(True, is_leap_year(j1.year))

utest(Date(2000, 2, 1), add, DateDelta(months=1), j1)
utest(Date(2002, 2, 28), add, DateDelta(months=1), Date(2002, 1, 31))

utest(DateDelta(years=2, months=2), add, DateDelta(years=1, months=1), DateDelta(years=1, months=1))
