# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from datetime import date as Date, datetime as DateTime, timedelta
from typing import Iterator


sec_per_min = 60
sec_per_hour = sec_per_min * 60
sec_per_day = sec_per_hour * 24

months = ('January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December')


def parse_datetime(string: str, fmt='%Y-%m-%d %H:%M:%S') -> DateTime:
  return DateTime.strptime(string, fmt)


def parse_date(string: str, fmt='%Y-%m-%d') -> Date:
  return DateTime.strptime(string, fmt).date()


def days_from(date_: Date, days: int) -> Date:
  return date_ + timedelta(days=days)

def next_day(date_: Date) -> Date:
  return date_ + timedelta(days=1)

def next_week(date_: Date) -> Date:
  return date_ + timedelta(days=7)


def days_range(start: Date, end: Date, step: int=1) -> Iterator[Date]:
  d = start
  while d < end:
    yield d
    d = days_from(d, days=step)


def months_range(start: Date, end: Date) -> Iterator[Date]:
  '''
  Note: this will fail for days > 28 due to February.
  '''
  d = start
  while d < end:
    yield d
    d = d.replace(year=d.year+1, month=1) if d.month == 12 else d.replace(month=d.month+1)
