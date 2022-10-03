# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from datetime import (date as Date, datetime as DateTime, time as Time, timedelta as TimeDelta, timezone as TimeZone,
  tzinfo as TZInfo)
from typing import TypeVar


sec_per_min = 60
sec_per_hour = sec_per_min * 60
sec_per_day = sec_per_hour * 24

months = ('January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December')

month_days = {
  1: 31,
  2: 28,
  3: 31,
  4: 30,
  5: 31,
  6: 30,
  7: 31,
  8: 31,
  9: 30,
  10: 31,
  11: 30,
  12: 31,
}


def days_in_year(year:int) -> int:
  if year % 4: return 365
  if year % 100: return 366
  if year % 400: return 365
  return 366


def is_leap_year(year:int) -> bool:
  return not bool((year%4) and (year%100 or not (year%400)))


DateLike = TypeVar('DateLike', Date, DateTime)


class DateDelta:

  def __init__(self, years:int=0, months:int=0):
    self.years = years
    self.months = months

  def __repr__(self) -> str:
    return f'{type(self).__name__}(years={self.years!r}, months={self.months!r})'

  def __add__(self, other:DateLike) -> DateLike:
    carry_years, month0 = divmod(other.month + self.months - 1, 12)
    year = other.year + self.years + carry_years
    month = month0 + 1
    if month == 2 and other.day == 29 and not is_leap_year(year):
      return other.replace(year=year, month=month, day=28)
    else:
      return other.replace(year=year, month=month)


def parse_datetime(string: str, fmt='%Y-%m-%d %H:%M:%S') -> DateTime:
  return DateTime.strptime(string, fmt)


def parse_date(string: str, fmt='%Y-%m-%d') -> Date:
  return DateTime.strptime(string, fmt).date()


def dt_for_utc_ts(ts:float) -> DateTime:
  return DateTime.fromtimestamp(ts, TimeZone.utc)


def next_day(date_: DateLike) -> DateLike:
  return date_ + TimeDelta(days=1)

def next_week(date_: DateLike) -> DateLike:
  return date_ + TimeDelta(days=7)
