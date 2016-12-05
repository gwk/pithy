# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from datetime import date, datetime, timedelta
from typing import Iterator


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


def days_range(start: date, end: date, step=int) -> Iterator[date]:
  d = start
  while d < end:
    yield d
    d = days_from(d, days=step)
