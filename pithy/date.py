# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from datetime import *
from typing import Iterator


months = ('January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December')


def parse_datetime(string: str, fmt='%Y-%m-%d %H:%M:%S') -> datetime:
  return datetime.strptime(string, fmt)


def parse_date(string: str, fmt='%Y-%m-%d') -> date:
  return datetime.strptime(string, fmt).date()


def days_from(date_: date, days: int) -> date:
  return date_ + timedelta(days=days)

def next_day(date_: date) -> date:
  return date_ + timedelta(days=1)

def next_week(date_: date) -> date:
  return date_ + timedelta(days=7)


def days_range(start: date, end: date, step: int=1) -> Iterator[date]:
  d = start
  while d < end:
    yield d
    d = days_from(d, days=step)


def months_range(start: date, end: date) -> Iterator[date]:
  '''
  Note: this will fail for days > 28 due to February.
  '''
  d = start
  while d < end:
    yield d
    d = d.replace(year=d.year+1, month=1) if d.month == 12 else d.replace(month=d.month+1)
