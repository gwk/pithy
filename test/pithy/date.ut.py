# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from operator import add, sub

from pithy.date import Date, DateDelta, DateRange, is_leap_year
from utest import utest, utest_seq, utest_symmetric, utest_val


y2k = Date(2000, 1, 1)
utest_val(True, is_leap_year(y2k.year))

utest_symmetric(utest, Date(2000, 2, 1), add, DateDelta(months=1), Date(2000, 1, 1))
utest_symmetric(utest, Date(2002, 2, 28), add, DateDelta(months=1), Date(2002, 1, 31))

utest(Date(1999, 12, 1), sub, Date(2000, 1, 1), DateDelta(months=1))

utest(DateDelta(years=2, months=2), add, DateDelta(years=1, months=1), DateDelta(years=1, months=1))


utest_seq([Date(2000, 1, 1), Date(2000, 2, 1), Date(2000, 3,1)],
  DateRange, Date(2000, 1, 1), Date(2000, 4, 1), step=DateDelta(months=1))
